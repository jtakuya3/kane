import { defineConfig, loadEnv } from 'vite';
import type { ProxyOptions, UserConfigExport } from 'vite';
import react from '@vitejs/plugin-react';
import * as path from 'path';

export default defineConfig(({ mode }): UserConfigExport => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  
  if (!env.VITE_API_BASE_URL) {
    throw new Error('VITE_API_BASE_URL must be set');
  }

  const proxy: Record<string, ProxyOptions> = {
    '/auth': {
      target: env.VITE_API_BASE_URL,
      changeOrigin: true,
      secure: false
    },
    '/api': {
      target: env.VITE_API_BASE_URL,
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
