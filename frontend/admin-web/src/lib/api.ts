import { createApiClient, type HealthResponse } from '@shopdesk/shared';

export const api = createApiClient({ baseURL: import.meta.env.VITE_API_BASE_URL ?? '' });

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await api.get<HealthResponse>('/api/health', {
    // A 503 still carries a health body ({db: "error"}); don't treat it as a network failure.
    validateStatus: (status) => status === 200 || status === 503,
  });
  return res.data;
}
