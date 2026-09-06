import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Fixed at 3000 (Vite's default 5173 doesn't match) so it matches
  // backend/main.py's CORS allowlist (localhost:3000 / 127.0.0.1:3000).
  server: {
    port: 3000,
  },
})
