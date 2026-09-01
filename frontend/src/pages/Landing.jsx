import {
  Activity, ArrowDown, ArrowRight, BarChart3, Bot, CheckCircle2,
  ChevronRight, CircleDollarSign, Database, GitBranch, Radar, RefreshCw,
  ShieldAlert, Sparkles, WalletCards, Webhook,
} from 'lucide-react';
import { Overview } from './Overview';
import { navigate } from '../hooks/useHashRoute';
import { Aurora } from '../components/Aurora';

const features = [
  [CircleDollarSign, 'Payment Monitoring', 'Track payment activity, success and failure rates, methods, amounts, and payment events.'],
  [Activity, 'Checkout Intelligence', 'Monitor checkout attempts, conversion, drop-offs, and failed checkout activity.'],
  [ShieldAlert, 'Anomaly Detection', 'Detect unusual payment and checkout patterns using deterministic operational rules.'],
  [Bot, 'AI Operations Agent', 'Analyze detected issues and provide human-readable explanations and evidence.'],
  [RefreshCw, 'Recovery Actions', 'Generate actionable recovery recommendations for failed payments and abandoned checkouts.'],
  [WalletCards, 'UPI Mandates', 'Track recurring-payment mandate lifecycle across pending, active, failed, and cancelled states.'],
  [BarChart3, 'Reports', 'Provide operational summaries, trends, failure analysis, recovery status, and comparisons.'],
];

const loop = [
  ['MONITOR', 'Track payment activity'],
  ['DETECT', 'Identify abnormal behavior'],
  ['UNDERSTAND', 'AI explains the issue'],
  ['ACT', 'Recommend recovery actions'],
  ['MEASURE', 'Track results through reports'],
];

function scrollTo(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
}

function Mark() {
  return <span className="landing-mark"><Sparkles size={17} /></span>;
}

function Arrow() {
  return <ArrowRight className="landing-flow-arrow" size={16} />;
}

export function Landing() {
  return (
    <main className="landing-page">
      <nav className="landing-nav">
        <button className="landing-brand" onClick={() => scrollTo('top')}><Mark /><strong>PayPulse</strong></button>
        <div className="landing-links">
          <button onClick={() => scrollTo('features')}>Features</button>
          <button onClick={() => scrollTo('how-it-works')}>How It Works</button>
          <button onClick={() => scrollTo('architecture')}>Architecture</button>
        </div>
      </nav>

      <section className="landing-hero" id="top">
        <Aurora colorStops={['#6C63FF', '#A78BFA', '#4F46E5']} amplitude={0.5} blend={0.35} speed={0.25} lightMode />
        <div className="landing-hero-overlay" />
        <div className="landing-hero-copy landing-hero-content">
          <div className="landing-kicker"><span className="landing-kicker-dot" /> AI-Powered Payment Operations</div>
          <h1>Payment operations,<br /><em>made intelligent.</em></h1>
          <p>An intelligent payment operations platform that monitors transactions, detects anomalies, explains payment issues, and recommends recovery actions.</p>
          <div className="landing-actions">
            <button className="btn btn-primary" onClick={() => navigate('/login')}>Login <ChevronRight size={14} /></button>
            <button className="btn btn-outline" onClick={() => scrollTo('architecture')}>View Architecture <ArrowRight size={14} /></button>
          </div>
          <div className="landing-proof"><CheckCircle2 size={14} /> Built for live, event-driven payment workflows</div>
        </div>
        <div className="landing-preview-wrap landing-hero-content" aria-label="Live PayPulse dashboard preview">
          <div className="landing-preview-label"><span className="landing-live-dot" /> Live workspace preview</div>
          <div className="landing-preview-screen"><Overview /></div>
        </div>
      </section>

      <section className="landing-section landing-value" id="how-it-works">
        <div className="landing-section-heading">
          <span className="landing-eyebrow">The operating layer</span>
          <h2>From payment event to<br /><span>operational action.</span></h2>
          <p>PayPulse turns scattered payment signals into a clear path from monitoring to measurable recovery.</p>
        </div>
        <div className="landing-process">
          {['Payment Monitoring', 'Checkout Intelligence', 'Anomaly Detection', 'AI Investigation', 'Recovery Recommendations', 'Reporting'].map((item, index) => (
            <div className="landing-process-item" key={item}><span>{String(index + 1).padStart(2, '0')}</span><strong>{item}</strong>{index < 5 ? <Arrow /> : null}</div>
          ))}
        </div>
      </section>

      <section className="landing-section" id="features">
        <div className="landing-section-heading centered"><span className="landing-eyebrow">One workspace</span><h2>Everything your payment team<br /><span>needs to move faster.</span></h2></div>
        <div className="landing-feature-grid">
          {features.map(([Icon, title, text]) => <article className="landing-feature-card" key={title}><div className="landing-icon"><Icon size={18} /></div><h3>{title}</h3><p>{text}</p></article>)}
        </div>
        <div className="landing-demo-note"><WalletCards size={17} /><p><strong>Demo environment:</strong> displayed mandate and transaction records are test data used to demonstrate the complete event-driven workflow. The underlying architecture is designed to process real payment and mandate events in production.</p></div>
      </section>

      <section className="landing-section landing-how" id="how-loop">
        <div className="landing-section-heading"><span className="landing-eyebrow">The PayPulse loop</span><h2>See the signal.<br /><span>Know the next move.</span></h2></div>
        <div className="landing-loop">{loop.map(([title, text], index) => <div className="landing-loop-item" key={title}><div className="landing-loop-number">0{index + 1}</div><strong>{title}</strong><p>{text}</p>{index < loop.length - 1 ? <ArrowDown size={15} /> : null}</div>)}</div>
      </section>

      <section className="landing-section" id="architecture">
        <div className="landing-section-heading centered"><span className="landing-eyebrow">Under the hood</span><h2>Architecture built for<br /><span>operational clarity.</span></h2><p>Easy to understand in one glance, ready to follow every event through the system.</p></div>
        <div className="landing-architecture">
          <div className="landing-arch-layer"><span>01 · DATA SOURCES</span><div><div><Webhook size={15} /> Razorpay payment events</div><div><Activity size={15} /> Checkout events</div><div><WalletCards size={15} /> UPI mandate events</div></div></div>
          <ArrowDown />
          <div className="landing-arch-layer"><span>02 · INGESTION</span><div><div><Webhook size={15} /> Razorpay Webhooks</div><div><GitBranch size={15} /> FastAPI Backend</div></div></div>
          <ArrowDown />
          <div className="landing-arch-layer"><span>03 · DATA LAYER</span><div><div><Database size={15} /> Supabase PostgreSQL</div></div></div>
          <ArrowDown />
          <div className="landing-arch-layer highlight"><span>04 · INTELLIGENCE</span><div><div>Payment Analytics</div><div>Checkout Intelligence</div><div>Anomaly Detection</div><div>AI Operations Agent</div><div>Recovery Engine</div><div>UPI Mandate Processing</div><div>Reporting</div></div></div>
          <ArrowDown />
          <div className="landing-arch-layer landing-arch-final"><span>05 · APPLICATION</span><div><div><Radar size={15} /> PayPulse Dashboard</div></div></div>
        </div>
      </section>

      <section className="landing-cta"><div><span className="landing-eyebrow">Ready when you are</span><h2>Bring payment operations<br />into one intelligent workspace.</h2></div><button className="btn btn-primary" onClick={() => navigate('/login')}>Open PayPulse Dashboard <ChevronRight size={14} /></button></section>
      <footer className="landing-footer"><button className="landing-brand" onClick={() => scrollTo('top')}><Mark /><strong>PayPulse</strong></button><span>AI-Powered Payment Operations</span></footer>
    </main>
  );
}
