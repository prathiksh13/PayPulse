import { request } from './client';

export const login = (email, password) =>
  request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });

export const getMe = () => request('/auth/me');

export const logout = () => request('/auth/logout', { method: 'POST', body: '{}' });

export const getDemoCredentials = () => request('/auth/demo-credentials');
