import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/input'
import { useAuth } from '@/lib/auth'
import { supabase } from '@/lib/supabase'

export function SignInPage() {
  const [mode, setMode] = useState<'in' | 'up'>('in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const { state } = useLocation()
  const { user } = useAuth()

  useEffect(() => { if (user) navigate('/', { replace: true }) }, [user, navigate])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    const result = mode === 'in'
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password })
    setBusy(false)
    if (result.error) return setError(result.error.message)
    if (mode === 'up' && !result.data.session) setNotice('Check your email to confirm your account, then sign in.')
  }

  return (
    <div className="mx-auto max-w-md py-6 lg:py-12">
      <h1 className="text-3xl font-light tracking-tight sm:text-4xl">{mode === 'in' ? 'Welcome back' : 'Create your account'}</h1>
      <p className="mb-6 mt-2 text-muted-foreground">{(state as { message?: string } | null)?.message ?? 'Save opportunities and come back to them on any device.'}</p>
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete={mode === 'in' ? 'current-password' : 'new-password'} required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            {mode === 'up' && <p className="mt-1.5 text-xs text-subtle">At least 8 characters.</p>}
          </div>
          {error && <p role="alert" className="rounded-lg bg-danger-soft p-3 text-sm text-danger">{error}</p>}
          {notice && <p role="status" className="rounded-lg bg-success-soft p-3 text-sm text-success">{notice}</p>}
          <Button type="submit" size="lg" className="w-full" disabled={busy}>{busy ? 'One moment' : mode === 'in' ? 'Sign in' : 'Create account'}</Button>
        </form>
      </Card>
      <p className="mt-4 text-center text-sm text-muted-foreground">
        {mode === 'in' ? 'New to OpenPath?' : 'Already have an account?'}{' '}
        <button onClick={() => { setMode(mode === 'in' ? 'up' : 'in'); setError(null); setNotice(null) }} className="min-h-11 font-medium text-accent">
          {mode === 'in' ? 'Create an account' : 'Sign in'}
        </button>
      </p>
    </div>
  )
}
