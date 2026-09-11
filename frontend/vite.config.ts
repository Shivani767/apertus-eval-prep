import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/apertus-eval-prep/',
  server: { port: 5173 },
})
