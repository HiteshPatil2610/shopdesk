import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

// Dev: the browser talks to this Vite server only; /api is proxied to the Flask POS API,
// so there are no CORS issues locally (architecture §11).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5174,
      strictPort: true,
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || 'http://localhost:5002',
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'jsdom',
    },
  };
});
