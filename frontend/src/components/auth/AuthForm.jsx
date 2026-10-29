import { useEffect, useRef, useState } from 'react'

import { useAuth } from '../../context/AuthContext'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID

function loadGoogleScript() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve()
    let script = document.querySelector('script[data-google-gsi]')
    if (!script) {
      script = document.createElement('script')
      script.src = 'https://accounts.google.com/gsi/client'
      script.async = true
      script.dataset.googleGsi = '1'
      document.head.appendChild(script)
    }
    script.addEventListener('load', resolve, { once: true })
    script.addEventListener('error', () => reject(new Error('Could not load Google sign-in.')), { once: true })
  })
}

export default function AuthForm({ onClose, message = '' }) {
  const { signInWithGoogle } = useAuth()
  const buttonRef = useRef(null)
  const [error, setError] = useState(
    GOOGLE_CLIENT_ID ? '' : 'Google sign-in is not set up yet. Add VITE_GOOGLE_CLIENT_ID to frontend/.env.',
  )
  const [busy, setBusy] = useState(false)

  // Google calls this with the token. We just pass it to the server.
  const handleCredential = useRef(null)
  handleCredential.current = async (response) => {
    setError('')
    setBusy(true)
    try {
      await signInWithGoogle(response.credential)
      onClose()
    } catch (err) {
      setError(err.message || 'Could not sign in. Try again.')
      setBusy(false)
    }
  }

  useEffect(() => {
    function closeOnEscape(event) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return undefined
    let cancelled = false
    loadGoogleScript()
      .then(() => {
        if (cancelled || !buttonRef.current) return
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => handleCredential.current(response),
        })
        window.google.accounts.id.renderButton(buttonRef.current, {
          theme: 'outline',
          size: 'large',
          shape: 'pill',
          text: 'continue_with',
          width: 280,
        })
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
    return () => { cancelled = true }
  }, [])

  return (
    <div className="auth-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose()
    }}>
      <section className="auth-panel" role="dialog" aria-modal="true" aria-labelledby="auth-title">
        <button type="button" className="auth-close" aria-label="Close sign-in" onClick={onClose}>×</button>
        <p className="eyebrow">Your onCamp account</p>
        <h2 id="auth-title">Sign in</h2>
        <p className="auth-intro">
          {message || 'Sign in with Google to see every upcoming event.'} You can still browse the next week without an account.
        </p>
        <div className="auth-google" ref={buttonRef} aria-busy={busy} />
        {busy && <p className="auth-status">Signing you in...</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </section>
    </div>
  )
}
