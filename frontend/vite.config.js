import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/run': 'http://127.0.0.1:8000',
      '/download-pdf': 'http://127.0.0.1:8000',
      '/download-docx': 'http://127.0.0.1:8000',
      '/history': 'http://127.0.0.1:8000',
    },
  },
})
