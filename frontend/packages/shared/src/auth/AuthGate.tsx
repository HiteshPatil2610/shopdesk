import { useAuth } from '@clerk/react';
import { useQuery } from '@tanstack/react-query';
import { createContext, useContext, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';

import { apiErrorCode, apiErrorMessage, type MeResponse } from '../api';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { useApi } from './ApiProvider';
import { WrongAppScreen } from './WrongAppScreen';

const MeContext = createContext<MeResponse | null>(null);

/** The signed-in ShopDesk user (role, name). Only available inside <AuthGate>. */
export function useMe(): MeResponse {
  const me = useContext(MeContext);
  if (!me) throw new Error('useMe must be used inside <AuthGate>');
  return me;
}

const ACCESS_DENIED_CODES = new Set(['ROLE_NOT_ALLOWED', 'NO_ROLE_ASSIGNED', 'ACCOUNT_INACTIVE']);

function FullScreen({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
      {children}
    </div>
  );
}

type Props = { appName: string; children: ReactNode };

/**
 * Signed out → /sign-in. Signed in → ask the API who we are (/api/auth/me).
 * The API decides access; this component only shows the result (spec 02 §9).
 */
export function AuthGate({ appName, children }: Props) {
  const { isLoaded, isSignedIn } = useAuth();
  const location = useLocation();
  const api = useApi();

  const me = useQuery({
    queryKey: ['me'],
    queryFn: async () => (await api.get<MeResponse>('/me')).data,
    enabled: Boolean(isLoaded && isSignedIn),
    retry: (count, err) => !ACCESS_DENIED_CODES.has(apiErrorCode(err) ?? '') && count < 2,
    staleTime: 60_000,
  });

  if (!isLoaded) {
    return (
      <FullScreen>
        <Spinner label="Loading" />
      </FullScreen>
    );
  }
  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />;
  }
  if (me.isPending) {
    return (
      <FullScreen>
        <Spinner label="Checking your account" />
        <p className="text-text-muted">Checking your account…</p>
      </FullScreen>
    );
  }
  if (me.isError) {
    const code = apiErrorCode(me.error);
    if (code && ACCESS_DENIED_CODES.has(code)) {
      return <WrongAppScreen appName={appName} message={apiErrorMessage(me.error)} />;
    }
    return (
      <FullScreen>
        <p className="text-lg font-semibold text-danger">Couldn't reach {appName}</p>
        <p className="max-w-md text-text-muted">{apiErrorMessage(me.error)}</p>
        <Button onClick={() => void me.refetch()}>Try again</Button>
      </FullScreen>
    );
  }
  return <MeContext.Provider value={me.data}>{children}</MeContext.Provider>;
}
