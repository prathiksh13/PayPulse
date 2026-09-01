import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Runs a fetcher (from src/api) that returns a normalized envelope.
 * Tracks loading / unavailable (404 = endpoint not implemented) / network error.
 */
export function useApi(fetcher, deps = [], options = {}) {
  const enabled = options.enabled !== false;
  const [state, setState] = useState({
    data: null,
    loading: enabled,
    unavailable: false,
    networkError: false,
    error: null,
    status: null,
  });
  const runRef = useRef(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const load = useCallback(async (opts = {}) => {
    const silent = opts.silent === true;
    const id = ++runRef.current;
    setState((s) => ({
      ...s,
      loading: silent ? s.loading : true,
      error: silent ? s.error : null,
      unavailable: silent ? s.unavailable : false,
      networkError: silent ? s.networkError : false,
    }));
    let res;
    try {
      res = await fetcherRef.current();
    } catch (err) {
      res = { ok: false, status: null, network: true, error: err?.message || 'Unexpected error' };
    }
    if (id !== runRef.current) return;
    if (!res.ok) {
      setState((s) => ({
        ...s,
        loading: false,
        data: null,
        unavailable: res.status === 404,
        networkError: !res.status,
        error: res.error || 'Request failed',
        status: res.status ?? null,
      }));
      return;
    }
    setState((s) => ({ ...s, loading: false, data: res.data ?? null, error: null, status: res.status }));
  }, []);

  useEffect(() => {
    if (!enabled) return undefined;
    load();
    return () => {
      runRef.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, enabled, ...deps]);

  const refresh = useCallback((opts) => load(opts), [load]);
  return { ...state, refresh };
}