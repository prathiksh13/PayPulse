import { useMemo, useState } from 'react';
import { LogIn, ShieldAlert, Sparkles, User, Lock, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Field, TextInput } from '../components/ui/Field';
import { Aurora } from '../components/Aurora';

export function Login() {
  const { login, loading: booting, demoCredentials } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const creds = useMemo(() => {
    if (!demoCredentials) return [];
    return [
      {
        label: 'Admin',
        role: demoCredentials.admin?.role || 'admin',
        email: demoCredentials.admin?.email || 'admin@paypulse.demo',
        password: demoCredentials.admin?.password || 'PayPulse@123',
      },
      {
        label: 'Analyst',
        role: demoCredentials.analyst?.role || 'analyst',
        email: demoCredentials.analyst?.email || 'analyst@paypulse.demo',
        password: demoCredentials.analyst?.password || 'PayPulse@123',
      },
    ];
  }, [demoCredentials]);

  const fill = (e, p) => {
    setEmail(e);
    setPassword(p);
    setError(null);
  };

  async function handleSubmit(ev) {
    ev.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    const res = await login(email.trim(), password);
    setSubmitting(false);
    if (!res?.ok) {
      setError(res?.error || 'Unable to sign in. Check the credentials and try again.');
    }
  }

  return (
    <main className="login-page">
      <Aurora colorStops={['#6C63FF', '#A78BFA', '#4F46E5']} amplitude={0.55} blend={0.4} speed={0.28} lightMode />
      <div className="login-overlay" />
      <div className="login-card">
        <div className="login-brand">
          <span className="landing-mark"><Sparkles size={18} /></span>
          <strong>PayPulse</strong>
        </div>
        <h1>Sign in to PayPulse</h1>
        <p className="login-subtitle">Payment operations workspace · Demo environment</p>

        <form className="login-form" onSubmit={handleSubmit}>
          <Field label="Email">
            <TextInput
              type="email"
              icon={User}
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </Field>
          <Field label="Password">
            <TextInput
              type="password"
              icon={Lock}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </Field>

          {error ? (
            <div className="login-error" role="alert">
              <AlertCircle size={15} /> {error}
            </div>
          ) : null}

          <button className="btn btn-primary btn-block" type="submit" disabled={submitting || booting}>
            {submitting ? 'Signing in…' : <><LogIn size={15} /> Sign in</>}
          </button>
        </form>

        {creds.length ? (
          <div className="login-demo">
            <div className="login-demo-heading"><ShieldAlert size={14} /> Demo accounts</div>
            {creds.map((c) => (
              <button
                type="button"
                className="login-demo-row"
                key={c.role}
                onClick={() => fill(c.email, c.password)}
              >
                <span className="login-demo-role">{c.label}</span>
                <span className="login-demo-creds">
                  <b>{c.email}</b>
                  <code>{c.password}</code>
                </span>
                <span className="login-demo-fill">Use</span>
              </button>
            ))}
          </div>
        ) : null}

        <p className="login-footnote">
          Admin can approve &amp; execute recovery actions; Analyst is view-only for recovery.
        </p>
      </div>
    </main>
  );
}
