import { defineConfig, ProxyOptions, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import * as path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  
  if (!env.VITE_API_BASE_URL) {
    throw new Error('VITE_API_BASE_URL must be set');
  }

  const proxyConfig: Record<string, ProxyOptions> = {
    '/auth': {
      target: env.VITE_API_BASE_URL,
      changeOrigin: true,
      secure: false,
      credentials: 'include'
    },
    '/api': {
      target: env.VITE_API_BASE_URL,
      changeOrigin: true,
      secure: false,
      credentials: 'include'
    }
  };

  return {
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
  };
});
