import { useState } from 'react'

import { useAuth } from '../../context/AuthContext'

export default function AccountMenu({ onSignIn }) {
  const { user, authLoading, signOut } = useAuth()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSignOut() {
    setBusy(true)
    setError('')
    try {
      await signOut()
    } catch (err) {
      setError(err.message || 'Could not sign out. Try again.')
    } finally {
      setBusy(false)
    }
  }

  if (authLoading) return <span className="account-loading">Checking account...</span>
  if (!user) return <button type="button" className="account-button" onClick={onSignIn}>Sign in</button>

  return (
    <div className="account-menu">
      <span className="account-email" title={user.email}>{user.email}</span>
      <button type="button" className="account-button account-button-light" disabled={busy} onClick={handleSignOut}>
        {busy ? 'Signing out...' : 'Sign out'}
      </button>
      {error && <span className="account-error" role="alert">{error}</span>}
    </div>
  )
}
