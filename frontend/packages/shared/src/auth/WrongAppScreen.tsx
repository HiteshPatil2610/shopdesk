import { useClerk } from '@clerk/react';

import { Button } from '../ui/Button';

type Props = { appName: string; message: string };

/** Shown when a valid Clerk user isn't allowed on this server (e.g. a cashier on Admin). */
export function WrongAppScreen({ appName, message }: Props) {
  const { signOut } = useClerk();
  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <div className="w-full max-w-md rounded-xl border border-border bg-surface p-8 text-center shadow-sm">
        <p className="text-4xl" aria-hidden="true">
          🔒
        </p>
        <h1 className="mt-4 text-xl font-bold">No access to {appName}</h1>
        <p className="mt-2 text-text-muted">{message}</p>
        <Button className="mt-6 w-full" onClick={() => void signOut({ redirectUrl: '/sign-in' })}>
          Sign out
        </Button>
      </div>
    </div>
  );
}
