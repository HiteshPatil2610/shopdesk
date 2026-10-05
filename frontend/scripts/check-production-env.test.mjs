import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateProductionEnv } from './check-production-env.mjs';
const env = {
  VERCEL_ENV: 'production',
  VITE_CLERK_PUBLISHABLE_KEY: `pk_live_${Buffer.from('clerk.example.com$').toString('base64')}`,
};
const policy =
  "script-src 'self' https://clerk.example.com https://*.protect.clerk.com; connect-src 'self' https://clerk.example.com https://*.protect.clerk.com:*; frame-src https://challenges.cloudflare.com https://*.protect.clerk.com; style-src https://fonts.googleapis.com; font-src https://fonts.gstatic.com; frame-ancestors 'none'";
const config = (csp = policy) => ({
  headers: [{ headers: [{ key: 'Content-Security-Policy', value: csp }] }],
});
test('production accepts same-origin API with live Clerk and required hosts', () => {
  assert.doesNotThrow(() => validateProductionEnv(env, config()));
  assert.doesNotThrow(() => validateProductionEnv({ VERCEL_ENV: 'preview' }, {}));
});
test('legacy API base URL is rejected in every environment', () => {
  for (const VERCEL_ENV of ['production', 'preview', undefined]) {
    assert.throws(
      () => validateProductionEnv({ ...env, VERCEL_ENV, VITE_API_BASE_URL: '' }, config()),
      /was removed/,
    );
  }
});
test('production rejects test keys and missing exact Clerk hosts', () => {
  assert.throws(() =>
    validateProductionEnv({ ...env, VITE_CLERK_PUBLISHABLE_KEY: 'pk_test_fake' }, config()),
  );
  assert.throws(() => validateProductionEnv(env, { headers: [] }));
  assert.throws(() =>
    validateProductionEnv(env, config(policy.replaceAll('clerk.example.com', '*.example.com'))),
  );
});
test('required fraud/font hosts, self and frame protection cannot be removed', () => {
  for (const source of [
    "'self'",
    'https://*.protect.clerk.com',
    'https://*.protect.clerk.com:*',
    'https://challenges.cloudflare.com',
    'https://fonts.googleapis.com',
    'https://fonts.gstatic.com',
    "'none'",
  ]) {
    assert.throws(() => validateProductionEnv(env, config(policy.replaceAll(source, ''))));
  }
});
test('production script policy forbids inline scripts and eval', () => {
  for (const source of ["'unsafe-inline'", "'unsafe-eval'"]) {
    assert.throws(() =>
      validateProductionEnv(env, config(policy.replace('script-src', `script-src ${source}`))),
    );
  }
});
