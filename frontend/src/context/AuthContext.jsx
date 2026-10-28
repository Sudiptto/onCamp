import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { getCurrentUser, loginWithGoogle, logoutAccount } from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)

  useEffect(() => {
    let active = true
    getCurrentUser()
      .then((currentUser) => {
        if (active) setUser(currentUser)
      })
      .catch(() => {
        if (active) setUser(null)
      })
      .finally(() => {
        if (active) setAuthLoading(false)
      })
    return () => { active = false }
  }, [])

  const signInWithGoogle = useCallback(async (credential) => {
    const result = await loginWithGoogle(credential)
    setUser(result.user)
    return result.user
  }, [])

  const signOut = useCallback(async () => {
    await logoutAccount()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, authLoading, signInWithGoogle, signOut }),
    [user, authLoading, signInWithGoogle, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
