import { createContext, useContext, useCallback, useEffect, useState } from 'react';
import { login as apiLogin, getMe, logout as apiLogout, getDemoCredentials } from '../api/auth';
import { getAccessToken, setTokens, clearTokens } from '../auth/token';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booted, setBooted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [demoCredentials, setDemoCredentials] = useState(null);

  useEffect(() => {
    let active = true;

    async function boot() {
      const token = getAccessToken();
      if (!token) {
        if (active) {
          setBooted(true);
          setLoading(false);
        }
        return;
      }
      const res = await getMe();
      if (!active) return;
      if (res.ok) {
        setUser({
          ...res.data,
          role: res.data?.role || 'analyst',
        });
      } else {
        clearTokens();
      }
      if (active) {
        setBooted(true);
        setLoading(false);
      }
    }

    getDemoCredentials().then((r) => {
      if (active && r.ok) setDemoCredentials(r.data);
    });

    boot();
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await apiLogin(email, password);
    if (!res.ok) return res;
    setTokens(res.data.access_token, res.data.refresh_token);
    const me = await getMe();
    const profile = me.ok ? me.data : res.data.user;
    setUser({
      ...profile,
      role: profile?.role || 'analyst',
    });
    return { ok: true };
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    clearTokens();
    setUser(null);
  }, []);

  const value = {
    user,
    isAuthenticated: Boolean(user),
    isAdmin: user?.role === 'admin',
    isAnalyst: user?.role === 'analyst',
    role: user?.role || null,
    booted,
    loading,
    demoCredentials,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
