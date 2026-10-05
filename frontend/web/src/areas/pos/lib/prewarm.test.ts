import { afterEach, describe, expect, it, vi } from 'vitest';

import { prewarm } from './prewarm';

describe('prewarm', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('pings the health endpoint without throwing when it fails', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('offline'));
    vi.stubGlobal('fetch', fetchMock);
    expect(() => prewarm('https://pos-api.example')).not.toThrow();
    expect(fetchMock).toHaveBeenCalledWith('https://pos-api.example/health', {
      method: 'GET',
      cache: 'no-store',
    });
  });
});
