import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const [domain, clerkHost] = process.argv.slice(2);
const hostname = /^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/i;
if (!domain || !clerkHost || !hostname.test(domain) || !hostname.test(clerkHost) || !domain.includes('.') || !clerkHost.includes('.')) {
  throw new Error('Usage: node scripts/security/configure-web-headers.mjs example.com clerk.example.com (hostnames only)');
}
const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
{
  const csp = `default-src 'self'; script-src 'self' https://${clerkHost} https://challenges.cloudflare.com https://*.protect.clerk.com; connect-src 'self' https://${clerkHost} https://*.protect.clerk.com:*; img-src 'self' data: blob: https://img.clerk.com https://res.cloudinary.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; frame-src 'self' https://challenges.cloudflare.com https://*.protect.clerk.com; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'`;
  const headers = Object.entries({
    'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': csp,
  }).map(([key, value]) => ({ key, value }));
  const path = resolve(root, 'vercel.json');
  const config = JSON.parse(readFileSync(path, 'utf8'));
  config.headers = [{ source: '/((?!api(?:/|$)).*)', headers }];
  writeFileSync(path, JSON.stringify(config, null, 2) + '\n');
}
console.log('Generated production security headers for the single web app. Review and commit before deployment.');
