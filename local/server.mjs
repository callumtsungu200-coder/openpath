// Local stand-in for Supabase: real Postgres plus the two API surfaces the web app uses
// (/rest/v1/rpc and /auth/v1). Queries run as anon or authenticated, so RLS and grants apply
// exactly as in production. Never deploy this: its tokens are not secure.
import { createHash, randomBytes, scryptSync, timingSafeEqual } from 'node:crypto'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PGlite } from '@electric-sql/pglite'
import { pg_trgm } from '@electric-sql/pglite/contrib/pg_trgm'
import { PGLiteSocketServer } from '@electric-sql/pglite-socket'

const here = path.dirname(fileURLToPath(import.meta.url))
const dataDir = path.join(here, '.local-pg')
const PG_PORT = 54329
const API_PORT = 54321
const fresh = !existsSync(path.join(dataDir, 'PG_VERSION'))

const db = new PGlite(dataDir, { extensions: { pg_trgm } })
await db.waitReady

if (fresh) await db.exec(readFileSync(path.join(here, 'auth-stub.sql'), 'utf8'))
const migrations = path.join(here, '..', 'supabase', 'migrations')
const files = readdirSync(migrations).sort()
const tracked = (await db.query(`select to_regclass('public.local_migrations') as t`)).rows[0].t
await db.exec('create table if not exists public.local_migrations (file text primary key)')
// A database from before tracking began already has the first migration.
if (!fresh && !tracked) await db.query('insert into public.local_migrations values ($1)', [files[0]])
const applied = new Set((await db.query('select file from public.local_migrations')).rows.map((r) => r.file))
for (const file of files.filter((f) => !applied.has(f))) {
  await db.exec(readFileSync(path.join(migrations, file), 'utf8'))
  await db.query('insert into public.local_migrations values ($1)', [file])
  console.log(`Applied ${file}`)
}

// The worker connects here over the normal Postgres protocol.
const socketServer = new PGLiteSocketServer({ db, port: PG_PORT, host: '127.0.0.1', maxConnections: 20 })
await socketServer.start()

const b64 = (v) => Buffer.from(JSON.stringify(v)).toString('base64url')
const makeToken = (user) => {
  const body = b64({ sub: user.id, email: user.email, role: 'authenticated', exp: Math.floor(Date.now() / 1000) + 86400 })
  const head = b64({ alg: 'none', typ: 'JWT' })
  return `${head}.${body}.${createHash('sha256').update(head + body).digest('base64url')}`
}
const readToken = (req) => {
  const token = (req.headers.authorization ?? '').replace('Bearer ', '')
  const [head, body, sig] = token.split('.')
  if (!body || sig !== createHash('sha256').update(head + body).digest('base64url')) return null
  const claims = JSON.parse(Buffer.from(body, 'base64url').toString())
  return claims.exp > Date.now() / 1000 ? claims : null
}
const hashPassword = (password, salt = randomBytes(16).toString('hex')) =>
  `${salt}:${scryptSync(password, salt, 32).toString('hex')}`
const checkPassword = (password, stored) => {
  const [salt, hash] = stored.split(':')
  return timingSafeEqual(Buffer.from(hash, 'hex'), scryptSync(password, salt, 32))
}
const session = (row) => {
  const user = { id: row.id, aud: 'authenticated', role: 'authenticated', email: row.email, app_metadata: {}, user_metadata: {}, created_at: row.created_at }
  return { access_token: makeToken(row), refresh_token: Buffer.from(row.id).toString('base64url'), token_type: 'bearer', expires_in: 86400, expires_at: Math.floor(Date.now() / 1000) + 86400, user }
}

async function rpc(fn, params, claims) {
  if (!/^[a-z_]+$/.test(fn)) throw Object.assign(new Error('Bad function name'), { status: 404 })
  const keys = Object.keys(params).filter((k) => /^[a-z_]+$/.test(k))
  const args = keys.map((k, i) => `${k} => $${i + 1}`).join(', ')
  return db.transaction(async (tx) => {
    await tx.query(`set local role ${claims ? 'authenticated' : 'anon'}`)
    await tx.query(`select set_config('request.jwt.claims', $1, true)`, [JSON.stringify(claims ?? {})])
    // Arrays go as Postgres array text, which also covers arrays of enums.
    const values = keys.map((k) => (Array.isArray(params[k]) ? `{${params[k].map((v) => JSON.stringify(v)).join(',')}}` : params[k]))
    const result = await tx.query(`select public.${fn}(${args}) as value`, values)
    return result.rows[0].value
  })
}

async function auth(route, query, body, req) {
  if (route === 'signup') {
    const { rows } = await db.query('insert into auth.users (email, encrypted_password) values ($1, $2) returning *', [body.email, hashPassword(body.password)])
    return session(rows[0])
  }
  if (route === 'token' && query.get('grant_type') === 'password') {
    const { rows } = await db.query('select * from auth.users where email = $1', [body.email])
    if (!rows[0] || !checkPassword(body.password, rows[0].encrypted_password)) {
      throw Object.assign(new Error('Invalid login credentials'), { status: 400, code: 'invalid_credentials' })
    }
    return session(rows[0])
  }
  if (route === 'token' && query.get('grant_type') === 'refresh_token') {
    const id = Buffer.from(body.refresh_token, 'base64url').toString()
    const { rows } = await db.query('select * from auth.users where id = $1', [id])
    if (!rows[0]) throw Object.assign(new Error('Invalid refresh token'), { status: 400 })
    return session(rows[0])
  }
  if (route === 'logout') return null
  if (route === 'user') {
    const claims = readToken(req)
    if (!claims) throw Object.assign(new Error('Not signed in'), { status: 401 })
    const { rows } = await db.query('select * from auth.users where id = $1', [claims.sub])
    return session(rows[0]).user
  }
  throw Object.assign(new Error('Not found'), { status: 404 })
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Headers', '*')
  res.setHeader('Access-Control-Allow-Methods', '*')
  if (req.method === 'OPTIONS') return res.writeHead(204).end()
  const send = (status, value) => {
    res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' })
    res.end(value === undefined || value === null ? 'null' : JSON.stringify(value))
  }
  try {
    const chunks = []
    for await (const chunk of req) chunks.push(chunk)
    const body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : {}
    const url = new URL(req.url, 'http://localhost')
    const rpcMatch = url.pathname.match(/^\/rest\/v1\/rpc\/(\w+)$/)
    const authMatch = url.pathname.match(/^\/auth\/v1\/(\w+)$/)
    if (rpcMatch) return send(200, await rpc(rpcMatch[1], body, readToken(req)))
    if (authMatch) return send(200, await auth(authMatch[1], url.searchParams, body, req))
    send(404, { message: 'Not found' })
  } catch (e) {
    const status = e.status ?? (e.code === '42501' || e.code === '28000' ? 403 : 400)
    send(status, { message: e.message, code: e.code, msg: e.message, error_code: e.code })
  }
})
server.listen(API_PORT, '127.0.0.1', () => {
  console.log(`API ready at http://127.0.0.1:${API_PORT}`)
  console.log(`Worker DATABASE_URL=postgresql://postgres@127.0.0.1:${PG_PORT}/postgres?sslmode=disable`)
})

const stop = async () => { server.close(); await socketServer.stop(); await db.close(); process.exit(0) }
process.on('SIGINT', stop)
process.on('SIGTERM', stop)
