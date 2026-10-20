import { useCallback, useEffect, useRef, useState } from 'react';

export type AsyncStatus = 'loading' | 'success' | 'error';

/** Loads data keyed by `key`; a new key (or retry) starts a fresh load and cancels the old one. */
export function useAsyncData<T>(key: string, load: (signal: AbortSignal) => Promise<T>) {
  const [attempt, setAttempt] = useState(0);
  const fullKey = `${key}#${attempt}`;
  const [state, setState] = useState<{ key: string; data?: T; error?: string } | null>(null);
  const loadRef = useRef(load);

  useEffect(() => {
    loadRef.current = load;
  });

  useEffect(() => {
    const controller = new AbortController();
    loadRef
      .current(controller.signal)
      .then((data) => setState({ key: fullKey, data }))
      .catch((err) => {
        if (controller.signal.aborted) return;
        setState({
          key: fullKey,
          error: err instanceof Error && err.message ? err.message : 'Something went wrong.',
        });
      });
    return () => controller.abort();
  }, [fullKey]);

  const current = state?.key === fullKey ? state : null;
  const status: AsyncStatus = !current
    ? 'loading'
    : current.error !== undefined
      ? 'error'
      : 'success';
  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  return { status, data: current?.data, error: current?.error, retry };
}
