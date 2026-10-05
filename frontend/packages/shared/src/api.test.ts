import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { describe, expect, it, vi } from 'vitest';

import { apiErrorCode, apiErrorMessage, createApiClient } from './api';

function unauthorized(config: InternalAxiosRequestConfig, code: string) {
  return new AxiosError('401', 'ERR_BAD_REQUEST', config, null, {
    status: 401,
    statusText: 'Unauthorized',
    headers: {},
    config,
    data: { error: { code, message: 'Session expired' } },
  });
}

describe('createApiClient', () => {
  it('sends the Clerk token as a Bearer header', async () => {
    const client = createApiClient({ baseURL: '', getToken: async () => 'tok_1' });
    const seen: string[] = [];
    client.defaults.adapter = async (config) => {
      seen.push(String(config.headers.get('Authorization')));
      return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
    };
    await client.get('/api/x');
    expect(seen).toEqual(['Bearer tok_1']);
  });

  it('retries once with a fresh token when the token expired', async () => {
    const getToken = vi.fn(async (opts?: { skipCache?: boolean }) =>
      opts?.skipCache ? 'fresh' : 'stale',
    );
    const client = createApiClient({ baseURL: '', getToken });
    let calls = 0;
    client.defaults.adapter = async (config) => {
      calls += 1;
      if (calls === 1) throw unauthorized(config, 'TOKEN_EXPIRED');
      return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config };
    };
    const res = await client.get('/api/x');
    expect(res.data).toEqual({ ok: true });
    expect(calls).toBe(2);
    expect(getToken).toHaveBeenCalledWith({ skipCache: true });
  });

  it('does not retry on other 401s', async () => {
    const client = createApiClient({ baseURL: '', getToken: async () => 't' });
    let calls = 0;
    client.defaults.adapter = async (config) => {
      calls += 1;
      throw unauthorized(config, 'TOKEN_WRONG_APP');
    };
    await expect(client.get('/api/x')).rejects.toThrow();
    expect(calls).toBe(1);
  });
});

describe('error helpers', () => {
  it('reads code and message from the API error shape', () => {
    const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
    const err = unauthorized(config, 'ROLE_NOT_ALLOWED');
    expect(apiErrorCode(err)).toBe('ROLE_NOT_ALLOWED');
    expect(apiErrorMessage(err)).toBe('Session expired');
    expect(apiErrorMessage(new Error('x'), 'fallback')).toBe('fallback');
  });
});

it.each([
  ['/api/admin', '/products', '/api/admin/products'],
  ['/api/pos', '/products', '/api/pos/products'],
  ['/api/auth', '/me', '/api/auth/me'],
])('keeps same-origin requests inside their selected area: %s', (baseURL, url, expected) => {
  expect(createApiClient({ baseURL }).getUri({ url })).toBe(expected);
});
