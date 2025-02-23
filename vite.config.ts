import { defineConfig, ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';
import * as path from 'path';

const proxyConfig: Record<string, ProxyOptions> = {
  '/auth': {
    target: 'https://app-tigsgeal.fly.dev',
    changeOrigin: true,
    secure: false
  },
  '/api': {
    target: 'https://app-tigsgeal.fly.dev',
    changeOrigin: true,
    secure: false
  }
};

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    include: ['firebase/app', 'firebase/auth']
  },
  server: {
    host: true,
    proxy: proxyConfig
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
});
