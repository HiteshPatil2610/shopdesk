import axios, { type AxiosInstance } from 'axios';

/** Shape of every API error (code-standards §2). */
export type ApiErrorBody = {
  error: { code: string; message: string; details?: unknown };
};

export type HealthResponse = {
  status: 'ok';
  server: 'admin' | 'pos';
  db: 'ok' | 'error';
  version: string;
};

type ApiClientOptions = {
  /** Empty string = same origin (Vite proxy in dev). Production: the API's https URL. */
  baseURL: string;
  /** Returns a Clerk session token, or null when signed out (wired up in spec 02). */
  getToken?: () => Promise<string | null>;
};

export function createApiClient({ baseURL, getToken }: ApiClientOptions): AxiosInstance {
  const client = axios.create({ baseURL, timeout: 20_000 });
  client.interceptors.request.use(async (config) => {
    const token = getToken ? await getToken() : null;
    if (token) {
      config.headers.set('Authorization', `Bearer ${token}`);
    }
    return config;
  });
  return client;
}

/** Reads the API error message from an axios error, with a safe fallback. */
export function apiErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError<ApiErrorBody>(err)) {
    return err.response?.data?.error?.message ?? (err.response ? fallback : 'Server unreachable');
  }
  return fallback;
}
