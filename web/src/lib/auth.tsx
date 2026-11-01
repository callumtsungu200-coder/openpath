import type { User } from '@supabase/supabase-js'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api'
import { supabase } from './supabase'

interface AuthState {
  user: User | null
  ready: boolean
  isAdmin: boolean
  signOut: () => Promise<void>
}
const AuthContext = createContext<AuthState>({ user: null, ready: false, isAdmin: false, signOut: async () => {} })

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  const queryClient = useQueryClient()

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null)
      setReady(true)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, session) => setUser(session?.user ?? null))
    return () => data.subscription.unsubscribe()
  }, [])

  const profile = useQuery({ queryKey: ['profile', user?.id], queryFn: api.profile, enabled: Boolean(user) })

  const signOut = async () => {
    await supabase.auth.signOut()
    queryClient.removeQueries({ queryKey: ['saved'] })
    queryClient.removeQueries({ queryKey: ['saved-ids'] })
    queryClient.removeQueries({ queryKey: ['admin'] })
  }

  return (
    <AuthContext.Provider value={{ user, ready, isAdmin: Boolean(profile.data?.is_admin), signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
