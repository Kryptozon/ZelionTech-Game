import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Mini App is served under /app, so assets must resolve under that base.
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
})
