import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export function validateProductionEnv(env, config) {
  if (env.VERCEL_ENV !== 'production') return;
  const key = env.VITE_CLERK_PUBLISHABLE_KEY ?? '';
  if (!key.startsWith('pk_live_'))
    throw new Error('Production VITE_CLERK_PUBLISHABLE_KEY must be pk_live_');
  const api = new URL(env.VITE_API_BASE_URL ?? '');
  if (
    api.protocol !== 'https:' ||
    api.username ||
    api.password ||
    api.search ||
    api.hash ||
    !['', '/'].includes(api.pathname)
  )
    throw new Error('Production VITE_API_BASE_URL must be an exact HTTPS origin');
  const clerkHost = Buffer.from(key.slice(8), 'base64').toString('utf8').replace(/\$$/, '');
  if (!/^[a-z0-9.-]+$/i.test(clerkHost)) throw new Error('Invalid Clerk publishable key hostname');
  const csp =
    config.headers
      ?.flatMap((entry) => entry.headers)
      .find((header) => header.key === 'Content-Security-Policy')?.value ?? '';
  const directives = Object.fromEntries(
    csp.split(';').map((part) => {
      const [name, ...sources] = part.trim().split(/\s+/);
      return [name, sources];
    }),
  );
  if (
    !directives['script-src']?.includes(`https://${clerkHost}`) ||
    !directives['connect-src']?.includes(api.origin) ||
    !directives['connect-src']?.includes(`https://${clerkHost}`) ||
    !directives['frame-ancestors']?.includes("'none'")
  ) {
    throw new Error(
      'Production CSP must contain exact API/Clerk hosts. Run scripts/security/configure-web-headers.mjs with your production domain.',
    );
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  validateProductionEnv(process.env, JSON.parse(readFileSync('vercel.json', 'utf8')));
}
