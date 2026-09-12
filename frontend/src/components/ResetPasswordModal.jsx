import { useState } from 'react'
import { resetPassword } from '../api'

export default function ResetPasswordModal({ token, onSuccess, onClose }) {
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const data = await resetPassword(token, newPassword)
      onSuccess(data.user, data.token)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="auth-modal__close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h2>Reset your password</h2>
        <p className="auth-modal__subtitle">Choose a new password for your account.</p>
        <form onSubmit={handleSubmit}>
          <label>
            New password
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          <label>
            Confirm new password
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          {error && <p className="auth-modal__error">{error}</p>}
          <button type="submit" disabled={submitting}>
            {submitting ? 'Please wait...' : 'Reset password'}
          </button>
        </form>
      </div>
    </div>
  )
}
