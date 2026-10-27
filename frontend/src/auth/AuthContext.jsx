import { createContext, useContext, useEffect, useMemo, useState } from 'react'

import { login as loginRequest, logout as logoutRequest, me, register as registerRequest } from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    me()
      .then((session) => {
        if (!cancelled) setUser(session)
      })
      .finally(() => {
        if (!cancelled) setReady(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const value = useMemo(() => ({
    user,
    ready,
    async login(credentials) {
      const session = await loginRequest(credentials)
      setUser(session)
      return session
    },
    async register(credentials) {
      const session = await registerRequest(credentials)
      setUser(session)
      return session
    },
    async logout() {
      await logoutRequest()
      setUser(null)
    },
  }), [user, ready])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return value
}
