import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The browser talks to the dev server on one origin; this proxy forwards to the
// backend and injects the API key server-side (from SECUREDOC_API_KEY), so the
// key never appears in the frontend bundle or in browser storage.
const backend = process.env.SECUREDOC_API_KEY
  ? { target: 'http://127.0.0.1:8000', headers: { 'X-API-Key': process.env.SECUREDOC_API_KEY } }
  : { target: 'http://127.0.0.1:8000' }

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': backend,
      '/health': backend,
    },
  },
})
