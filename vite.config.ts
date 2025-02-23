import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    include: ['firebase/app', 'firebase/auth']
  },
  server: {
    proxy: {
      '/api': {
        target: 'https://app-tigsgeal.fly.dev',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
