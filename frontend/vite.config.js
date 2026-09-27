import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/run': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/ready': 'http://127.0.0.1:8000',
      '/history': 'http://127.0.0.1:8000',
      '/export': 'http://127.0.0.1:8000',
      '/download-pdf': 'http://127.0.0.1:8000',
      '/download-docx': 'http://127.0.0.1:8000',
      '/download-markdown': 'http://127.0.0.1:8000',
      '/workspace': 'http://127.0.0.1:8000',
      '/dossier': 'http://127.0.0.1:8000',
    },
  },
})
