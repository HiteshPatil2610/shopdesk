import { SignIn } from '@clerk/react';

type Props = { appName: string };

/** ShopDesk-branded page hosting Clerk's sign-in form. Sign-up is hidden (Invite-only). */
export function SignInPage({ appName }: Props) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-bg p-6">
      <div className="text-center">
        <p className="text-sm font-semibold tracking-widest text-text-muted uppercase">ShopDesk</p>
        <h1 className="text-2xl font-bold">{appName}</h1>
      </div>
      <SignIn
        routing="path"
        path="/sign-in"
        forceRedirectUrl="/"
        appearance={{
          variables: {
            colorPrimary: '#2563eb',
            borderRadius: '0.5rem',
            fontFamily: 'Inter, sans-serif',
          },
          elements: { footerAction: { display: 'none' } },
        }}
      />
    </main>
  );
}
