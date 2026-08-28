import { useEffect, useState } from 'react';

function parseHash() {
  const raw = window.location.hash.replace(/^#/, '');
  const [path = '', qs = ''] = raw.split('?');
  const clean = path.replace(/\/+$/, '') || '/';
  const query = new URLSearchParams(qs);
  const segs = clean.split('/').filter(Boolean);
  return { path: clean, segs, query };
}

export function navigate(to) {
  if (to === window.location.hash.replace(/^#/, '') || to === '') return;
  window.location.hash = to;
}

export function useHashRoute() {
  const [route, setRoute] = useState(() => parseHash());
  useEffect(() => {
    const onChange = () => {
      setRoute(parseHash());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}