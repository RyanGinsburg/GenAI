import { useState } from 'react'
import { loginUser, registerUser, requestPasswordReset } from '../api'

export default function AuthModal({ onClose, onAuthSuccess, initialMode = 'login' }) {
  const [mode, setMode] = useState(initialMode)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [forgotMessage, setForgotMessage] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    if (mode === 'forgot') {
      try {
        const data = await requestPasswordReset(email)
        setForgotMessage(data.message)
      } catch (err) {
        setError(err.message)
      } finally {
        setSubmitting(false)
      }
      return
    }

    try {
      const data =
        mode === 'login' ? await loginUser(email, password) : await registerUser(name, email, password)
      onAuthSuccess(data.user, data.token)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  function switchMode(newMode) {
    setMode(newMode)
    setError(null)
    setForgotMessage(null)
  }

  const titles = {
    login: 'Log in',
    register: 'Create an account',
    forgot: 'Reset your password',
  }
  const subtitles = {
    login: 'Log in to save clubs and keep track of what you find.',
    register: 'Sign up to start saving clubs to come back to later.',
    forgot: "Enter your email and we'll send you a link to reset your password.",
  }

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="auth-modal__close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h2>{titles[mode]}</h2>
        <p className="auth-modal__subtitle">{subtitles[mode]}</p>

        {mode === 'forgot' && forgotMessage ? (
          <p className="auth-modal__subtitle">{forgotMessage}</p>
        ) : (
          <form onSubmit={handleSubmit}>
            {mode === 'register' && (
              <label>
                Name
                <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
              </label>
            )}
            <label>
              Email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            {mode !== 'forgot' && (
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={8}
                  required
                />
              </label>
            )}
            {mode === 'login' && (
              <button
                type="button"
                className="auth-modal__forgot-link"
                onClick={() => switchMode('forgot')}
              >
                Forgot password?
              </button>
            )}
            {error && <p className="auth-modal__error">{error}</p>}
            <button type="submit" disabled={submitting}>
              {submitting
                ? 'Please wait...'
                : mode === 'login'
                  ? 'Log in'
                  : mode === 'register'
                    ? 'Sign up'
                    : 'Send reset link'}
            </button>
          </form>
        )}

        {mode !== 'forgot' && (
          <button
            type="button"
            className="auth-modal__switch"
            onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
          >
            {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Log in'}
          </button>
        )}
        {mode === 'forgot' && (
          <button type="button" className="auth-modal__switch" onClick={() => switchMode('login')}>
            Back to log in
          </button>
        )}
      </div>
    </div>
  )
}
