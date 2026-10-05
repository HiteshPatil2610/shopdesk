import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadEnv } from 'vite';

export function validateProductionEnv(env, config) {
  if (Object.hasOwn(env, 'VITE_API_BASE_URL'))
    throw new Error('VITE_API_BASE_URL was removed; use same-origin API paths');
  if (env.VERCEL_ENV !== 'production') return;
  const key = env.VITE_CLERK_PUBLISHABLE_KEY ?? '';
  if (!key.startsWith('pk_live_'))
    throw new Error('Production VITE_CLERK_PUBLISHABLE_KEY must be pk_live_');
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
    !directives['connect-src']?.includes("'self'") ||
    !directives['connect-src']?.includes(`https://${clerkHost}`) ||
    !directives['frame-ancestors']?.includes("'none'") ||
    !directives['script-src']?.includes('https://*.protect.clerk.com') ||
    !directives['connect-src']?.includes('https://*.protect.clerk.com:*') ||
    !directives['frame-src']?.includes('https://challenges.cloudflare.com') ||
    !directives['frame-src']?.includes('https://*.protect.clerk.com') ||
    !directives['style-src']?.includes('https://fonts.googleapis.com') ||
    !directives['font-src']?.includes('https://fonts.gstatic.com') ||
    directives['script-src']?.includes("'unsafe-inline'") ||
    directives['script-src']?.includes("'unsafe-eval'")
  ) {
    throw new Error(
      'Production CSP must contain self, the exact Clerk host and required fraud/font hosts. Run scripts/security/configure-web-headers.mjs.',
    );
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const rootConfig = fileURLToPath(new URL('../../vercel.json', import.meta.url));
  validateProductionEnv(
    { ...loadEnv('production', process.cwd(), 'VITE_'), ...process.env },
    JSON.parse(readFileSync(rootConfig, 'utf8')),
  );
}
