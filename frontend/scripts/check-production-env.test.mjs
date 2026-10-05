import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateProductionEnv } from './check-production-env.mjs';
const env = {
  VERCEL_ENV: 'production',
  VITE_CLERK_PUBLISHABLE_KEY: `pk_live_${Buffer.from('clerk.example.com$').toString('base64')}`,
  VITE_API_BASE_URL: 'https://admin-api.example.com',
};
const config = {
  headers: [
    {
      headers: [
        {
          key: 'Content-Security-Policy',
          value:
            "script-src 'self' https://clerk.example.com; connect-src 'self' https://clerk.example.com https://admin-api.example.com; frame-ancestors 'none'",
        },
      ],
    },
  ],
};
test('production deploy rejects test keys and missing exact CSP hosts', () => {
  assert.throws(() =>
    validateProductionEnv({ ...env, VITE_CLERK_PUBLISHABLE_KEY: 'pk_test_fake' }, config),
  );
  assert.throws(() => validateProductionEnv(env, { headers: [] }));
  assert.throws(() =>
    validateProductionEnv({ ...env, VITE_API_BASE_URL: 'http://api.example.com' }, config),
  );
  assert.doesNotThrow(() => validateProductionEnv(env, config));
  assert.doesNotThrow(() => validateProductionEnv({ VERCEL_ENV: 'preview' }, {}));
});
