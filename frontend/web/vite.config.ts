import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { loadEnv, type Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

/** Fail the build if the shell or POS static import graph includes admin modules. */
function areaChunkBoundary(): Plugin {
  return {
    name: 'shopdesk-area-chunk-boundary',
    generateBundle(_options, bundle) {
      const visited = new Set<string>();
      const inspect = (file: string) => {
        if (visited.has(file)) return;
        visited.add(file);
        const chunk = bundle[file];
        if (!chunk || chunk.type !== 'chunk') return;
        if (
          Object.keys(chunk.modules).some((id) =>
            id.replaceAll(String.fromCharCode(92), '/').includes('/areas/admin/'),
          )
        ) {
          this.error(`Admin JavaScript leaked into shell/POS static imports: ${file}`);
        }
        chunk.imports.forEach(inspect);
      };
      const chunks = Object.values(bundle).filter((chunk) => chunk.type === 'chunk');
      const pos = chunks.find((chunk) =>
        chunk.facadeModuleId
          ?.replaceAll(String.fromCharCode(92), '/')
          .endsWith('/areas/pos/router.tsx'),
      );
      if (!pos) this.error('POS lazy entry missing from the production build');
      inspect(pos.fileName);
      chunks.filter((chunk) => chunk.isEntry).forEach((chunk) => inspect(chunk.fileName));
    },
  };
}

// Dev: the browser talks to this Vite server only; /api is proxied to the single Flask API,
// so there are no CORS issues locally (architecture §11).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    build: { manifest: true },
    plugins: [react(), tailwindcss(), areaChunkBoundary()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || 'http://localhost:5001',
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'jsdom',
    },
  };
});
