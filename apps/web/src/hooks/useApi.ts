import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";

export interface AsyncState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  refreshing: boolean;
  reload: () => void;
  setData: (value: T | null) => void;
}

/**
 * Minimal, dependency-free async data hook with loading / error / refresh
 * states and an optional polling interval. Cancels in-flight requests on
 * unmount or dependency change.
 */
export function useApi<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
  options: { pollMs?: number; enabled?: boolean } = {},
): AsyncState<T> {
  const { pollMs, enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [refreshing, setRefreshing] = useState(false);
  const [nonce, setNonce] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    let active = true;
    const run = async (isRefresh: boolean) => {
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        const value = await loaderRef.current(controller.signal);
        if (!active) return;
        setData(value);
        setError(null);
      } catch (err) {
        if (!active) return;
        if (err instanceof ApiError && err.code === "cancelled") return;
        setError(
          err instanceof ApiError
            ? err
            : new ApiError("Unexpected client error.", { category: "unknown" }),
        );
      } finally {
        if (active) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    };
    void run(false);

    let timer: number | undefined;
    if (pollMs && pollMs > 0) {
      timer = window.setInterval(() => void run(true), pollMs);
    }
    return () => {
      active = false;
      controller.abort();
      if (timer) window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, pollMs, nonce, ...deps]);

  return { data, error, loading, refreshing, reload, setData };
}
