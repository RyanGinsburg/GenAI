import { useEffect, useRef } from 'react'
import { googleSignIn } from '../api'

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID

// Google Identity Services renders its own button into a DOM node rather
// than being a normal React-controlled element, so this wraps that
// imperative API instead of rendering our own button markup.
export default function GoogleSignInButton({ onSuccess, onError }) {
  const buttonRef = useRef(null)

  useEffect(() => {
    if (!CLIENT_ID) {
      // Not configured yet (see frontend/.env.example) - fail quietly,
      // the rest of the auth modal (email/password) still works.
      return
    }

    let cancelled = false
    let attempts = 0

    function tryInit() {
      if (cancelled) return
      if (!window.google?.accounts?.id) {
        // The GIS script tag is async/defer - it may not have loaded yet
        // by the time this component mounts. A few short retries covers
        // that without adding a real dependency to poll for script-load.
        attempts += 1
        if (attempts < 20) setTimeout(tryInit, 150)
        return
      }

      window.google.accounts.id.initialize({
        client_id: CLIENT_ID,
        callback: handleCredentialResponse,
      })
      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: 'outline',
        size: 'large',
        width: 300,
      })
    }

    async function handleCredentialResponse(response) {
      try {
        const data = await googleSignIn(response.credential)
        onSuccess(data.user, data.token)
      } catch (err) {
        onError(err.message)
      }
    }

    tryInit()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!CLIENT_ID) return null

  return <div className="google-signin-container" ref={buttonRef} />
}
