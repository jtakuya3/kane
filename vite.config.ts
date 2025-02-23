import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    include: ['firebase/app', 'firebase/auth']
  },
  server: {
    host: true,
    proxy: {
      '/auth': {
        target: 'https://app-tigsgeal.fly.dev',
        changeOrigin: true,
        secure: false,
        credentials: true
      },
      '/api': {
        target: 'https://app-tigsgeal.fly.dev',
        changeOrigin: true,
        secure: false,
        credentials: true
      }
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
})
