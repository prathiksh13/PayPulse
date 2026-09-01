const BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '');

import { getAccessToken } from '../auth/token';

export function qs(params = {}) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (Array.isArray(value)) {
      value.forEach((v) => sp.append(key, v));
      return;
    }
    sp.append(key, String(value));
  });
  const s = sp.toString();
  return s ? `?${s}` : '';
}

/**
 * Uniform fetch wrapper. Never throws for HTTP errors.
 * Returns:
 *   { ok:true,  status, data }                 on 2xx
 *   { ok:false, status, error }                on non-2xx (404 = endpoint not implemented)
 *   { ok:false, status:null, error, network }  on network failure / backend down
 */
export async function request(path, options = {}) {
  const { headers, ...rest } = options;
  const token = getAccessToken();
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};
  let requestBody = rest.body;
  if (rest.body && typeof rest.body !== 'string' && !(rest.body instanceof FormData)) {
    requestBody = JSON.stringify(rest.body);
    rest = { ...rest, body: requestBody };
  }
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...rest,
      headers: { 'Content-Type': 'application/json', ...authHeaders, ...(headers || {}) },
    });
    if (!res.ok) {
      let detail;
      try {
        detail = (await res.json())?.detail || res.statusText;
      } catch {
        detail = res.statusText;
      }
      return { ok: false, status: res.status, error: detail || res.statusText };
    }
    const data = await res.json().catch(() => null);
    return { ok: true, status: res.status, data };
  } catch (err) {
    return { ok: false, status: null, network: true, error: err?.message || 'Network error' };
  }
}