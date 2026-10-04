import { useEffect, useRef } from 'react';

/** Page-level keyboard shortcuts. Subscribes once; always calls the latest handler. */
export function useHotkeys(handler: (event: KeyboardEvent) => void) {
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  }, [handler]);
  useEffect(() => {
    const listener = (event: KeyboardEvent) => latest.current(event);
    document.addEventListener('keydown', listener);
    return () => document.removeEventListener('keydown', listener);
  }, []);
}
