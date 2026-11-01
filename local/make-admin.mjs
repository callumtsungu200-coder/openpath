// Usage: npm run make-admin -- you@example.com (the local server must be running)
import pg from 'pg'

const email = process.argv[2]
if (!email) throw new Error('Pass the email of an account that has already signed up')
const client = new pg.Client({ host: '127.0.0.1', port: 54329, user: 'postgres', database: 'postgres' })
await client.connect()
const { rowCount } = await client.query(
  'update public.profiles set is_admin = true where user_id = (select id from auth.users where email = $1)', [email])
console.log(rowCount ? `${email} is now an admin` : `No account found for ${email}`)
await client.end()
