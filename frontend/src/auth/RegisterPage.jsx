import { useState } from 'react'

import { useAuth } from './AuthContext'

export default function RegisterPage({ onLogin, onSuccess, onBack }) {
  const { register } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await register({ name, email, password })
      onSuccess()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page">
      <header className="masthead">
        <div className="masthead-inner">
          <div>
            <p className="eyebrow">Hunter College</p>
            <h1>onCamp</h1>
            <p className="lede">Create an account to save events.</p>
          </div>
        </div>
      </header>
      <main className="shell">
        <form className="auth-card" onSubmit={handleSubmit}>
          <h2>Create account</h2>
          <p className="auth-note">Demo account. It stays in this browser until the auth API is connected.</p>
          <label>
            Name
            <input
              type="text"
              autoComplete="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={6}
              required
            />
          </label>
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" className="auth-submit" disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
          <p className="auth-switch">
            Already have an account?{' '}
            <button type="button" onClick={onLogin}>Sign in</button>
          </p>
          <button type="button" className="auth-back" onClick={onBack}>
            Back to calendar
          </button>
        </form>
      </main>
    </div>
  )
}
