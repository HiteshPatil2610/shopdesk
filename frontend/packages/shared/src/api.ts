import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';

/** Shape of every API error (code-standards §2). */
export type ApiErrorBody = {
  error: { code: string; message: string; details?: unknown };
};

export type HealthResponse = {
  status: 'ok';
  app: 'shopdesk';
  db: 'ok' | 'error';
  version: string;
};

export type Role = 'admin' | 'manager' | 'cashier';

export type UserPublic = {
  id: number;
  username: string | null;
  full_name: string;
  email: string | null;
  role: Role;
  is_active: boolean;
  last_seen_at: string | null;
};

export type MeResponse = { user: UserPublic; areas: ('admin' | 'pos')[] };

/** Clerk's getToken; `skipCache` forces a fresh token after a 401. */
export type GetToken = (opts?: { skipCache?: boolean }) => Promise<string | null>;

type ApiClientOptions = {
  /** Same-origin base path: /api/auth, /api/admin or /api/pos. */
  baseURL: string;
  getToken?: GetToken;
};

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

const RETRYABLE_AUTH_CODES = new Set(['TOKEN_EXPIRED', 'TOKEN_INVALID']);

export function createApiClient({ baseURL, getToken }: ApiClientOptions): AxiosInstance {
  const client = axios.create({ baseURL, timeout: 20_000 });

  client.interceptors.request.use(async (config) => {
    const token = getToken ? await getToken() : null;
    if (token) {
      config.headers.set('Authorization', `Bearer ${token}`);
    }
    return config;
  });

  // Clerk tokens live ~60s. If one expired in flight, get a fresh one and retry once.
  client.interceptors.response.use(undefined, async (error: unknown) => {
    if (!axios.isAxiosError<ApiErrorBody>(error) || !getToken) throw error;
    const config = error.config as RetriableConfig | undefined;
    const code = error.response?.data?.error?.code ?? '';
    if (
      config &&
      !config._retried &&
      error.response?.status === 401 &&
      RETRYABLE_AUTH_CODES.has(code)
    ) {
      config._retried = true;
      await getToken({ skipCache: true });
      return client.request(config);
    }
    throw error;
  });

  return client;
}

/** The API error code (e.g. "ROLE_NOT_ALLOWED"), if the server sent one. */
export function apiErrorCode(err: unknown): string | null {
  if (axios.isAxiosError<ApiErrorBody>(err)) {
    return err.response?.data?.error?.code ?? null;
  }
  return null;
}

/** Reads the API error message from an axios error, with a safe fallback. */
export function apiErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError<ApiErrorBody>(err)) {
    return err.response?.data?.error?.message ?? (err.response ? fallback : 'Server unreachable');
  }
  return fallback;
}
