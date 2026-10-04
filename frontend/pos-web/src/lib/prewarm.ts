/** Fire-and-forget health call so the first real billing request doesn't pay the cold start. */
export function prewarm(apiBase: string): void {
  void fetch(`${apiBase}/api/health`, { method: 'GET', cache: 'no-store' }).catch(() => {
    // Ignore: AuthGate shows a proper error if the server is really down.
  });
}
