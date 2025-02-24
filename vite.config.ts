import { defineConfig, loadEnv } from 'vite';
import type { ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';
import * as path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  
  const apiBaseUrl = env.VITE_API_BASE_URL;
  if (!apiBaseUrl) {
    console.warn('Warning: VITE_API_BASE_URL is not set');
  }

  const proxy: Record<string, ProxyOptions> = {
    '/auth': {
      target: apiBaseUrl || 'http://localhost:8000',
      changeOrigin: true,
      secure: false
    },
    '/api': {
      target: apiBaseUrl || 'http://localhost:8000',
      changeOrigin: true,
      secure: false
    }
  };

  return {
    plugins: [react()],
    optimizeDeps: {
      include: ['firebase/app', 'firebase/auth']
    },
    server: {
      host: true,
      proxy
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src')
      }
    }
  };
});
