/** Rendered instead of the app when VITE_CLERK_PUBLISHABLE_KEY is missing. */
export function ClerkConfigError({ appDir }: { appDir: string }) {
  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-lg rounded-xl border border-danger/40 bg-surface p-6">
        <h1 className="text-lg font-bold text-danger">Sign-in isn't configured</h1>
        <p className="mt-2 text-text-muted">
          Create <code className="font-mono">frontend/{appDir}/.env.development.local</code> with:
        </p>
        <pre className="mt-3 rounded-lg bg-bg p-3 font-mono text-sm">
          VITE_CLERK_PUBLISHABLE_KEY=pk_test_…
        </pre>
        <p className="mt-3 text-sm text-text-muted">
          Then restart the dev server. See SETUP_GUIDE.md §8.
        </p>
      </div>
    </main>
  );
}
