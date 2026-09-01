# PayPulse Project Logic

This document explains how the AI Payment Operations Agent works from browser startup through payment ingestion, analytics, anomaly detection, recovery, and AI responses.

## 1. Product Purpose

PayPulse is an operations control plane for a merchant using Razorpay. Its purpose is to answer four questions from stored payment activity:

1. What happened to payments and checkout sessions?
2. Where are failures, drop-offs, or unusual patterns occurring?
3. Which failed payments may be recoverable, and what should happen next?
4. Can an operator ask those questions in natural language without the system inventing data?

The system is event-driven at the data boundary, database-backed for reporting, and policy-controlled for recovery actions.

## 2. High-Level Architecture

```text
Browser (React + Vite)
        |
        | fetch requests under /api
        v
FastAPI application
        |
        +-- Routers: HTTP validation and response shaping
        +-- Services: ingestion, analytics, anomalies, recovery, AI
        +-- SQLAlchemy: persistence and queries
        v
SQLite by default or PostgreSQL
        ^
        |
Razorpay webhooks / Checkout SDK / Razorpay REST API
```

The backend entry point is `backend/app/main.py`. It loads configuration, enables CORS, creates database tables at startup, and mounts all routers under `/api`.

## 3. Frontend Execution Flow

### Startup and routing

`frontend/src/main.jsx` mounts the React application in `StrictMode`. `App.jsx` wraps the application in `ToastProvider` and `AppProvider`.

`AppContext` combines:

- `useHashRoute()` for route state
- merchant/workspace state
- selected date range
- dashboard settings

The route is read from `window.location.hash`, so navigation does not require a server-side route fallback. `/` and `/landing` render the landing page. Dashboard routes render a shared sidebar/topbar shell and select a page from the `PAGES` map.

### API request flow

All frontend requests are centralized in `frontend/src/api/index.js`. Components do not scatter raw `fetch()` calls throughout pages.

1. An endpoint helper builds a path and query string.
2. `api/client.js` prefixes the path with `VITE_API_URL` or `/api`.
3. `request()` returns a normalized object instead of throwing for HTTP failures.
4. `useApi()` tracks loading, data, HTTP errors, 404/unavailable state, and network failures.
5. Pages choose an honest empty/error state when data is unavailable.

This is why a new local database normally shows empty charts and “waiting for events” messaging instead of fake payment activity.

### Persistence in the browser

`AppContext` stores the merchant, date range, and settings using `useLocalStorage`:

- `pulseops.merchant`
- `pulseops.range`
- `pulseops.settings`

This gives the UI a usable local state even when no backend settings have been loaded. Backend settings are persisted separately in the `app_settings` table.

## 4. Backend Configuration and Database

`backend/app/config.py` loads `backend/.env` using `python-dotenv`.

Important configuration values:

| Variable | Role |
| --- | --- |
| `DATABASE_URL` | SQLite or PostgreSQL connection string |
| `RAZORPAY_KEY_ID` | Public provider key used by checkout responses |
| `RAZORPAY_KEY_SECRET` | Server-only Razorpay API credential |
| `RAZORPAY_WEBHOOK_SECRET` | Server-only HMAC verification secret |
| `RAZORPAY_API_BASE` | Razorpay API base URL |
| `GROQ_API_KEY` | Enables the optional LLM agent path |
| `GROQ_MODEL` | Groq model name |
| `GROQ_API_BASE` | OpenAI-compatible Groq endpoint |
| `ANOMALY_MIN_TRANSACTIONS` | Minimum failed transactions for spike detection |
| `FRONTEND_ORIGIN` | Comma-separated CORS origins |

Invalid or missing database schemes fall back to SQLite. `database.py` creates the SQLAlchemy engine and session factory. `init_db()` imports the models and calls `Base.metadata.create_all()` during FastAPI startup.

There are no migrations in this milestone, so schema evolution should be handled carefully before production use.

## 5. Data Model

The main tables in `backend/app/models.py` are:

- `payments`: normalized current state for each provider payment
- `payment_events`: immutable-ish provider event stream with deduplication key
- `payment_attempts`: attempt-level status, method, transaction, and failure data
- `upi_mandates`: UPI mandate state and customer metadata
- `mandate_events`: mandate event history
- `checkout_sessions`: session-level funnel state and duration
- `checkout_events`: checkout telemetry such as OTP and payment stages
- `anomalies`: persisted daily active/resolved detection results
- `ai_decisions`: questions, answers, tool calls, model, and latency
- `recovery_actions`: recommended or executable operations
- `recovery_outcomes`: result of each attempted recovery operation
- `audit_logs`: actor, action, entity, result, and request context
- `daily_reports`: persisted generated report metrics
- `app_settings`: JSON settings keyed by setting name

Raw Razorpay payloads are retained in JSON columns so the normalized columns can be audited against provider data.

## 6. Payment Ingestion Logic

### Razorpay webhook path

The endpoint is `POST /api/webhooks/razorpay`. The router verifies the request signature with HMAC-SHA256 before passing the JSON payload to `services/webhook_ingest.py`.

`process_webhook()` performs the following steps:

1. Reject a malformed payload without an `event` field.
2. Build a deterministic event ID from event name, timestamp, and provider entity IDs.
3. Check the unique `PaymentEvent.event_id` to make processing idempotent.
4. Store the incoming event and raw payload.
5. Route the event to payment, mandate, order, payment-link, or refund handling.
6. Normalize provider amounts from paise to rupees.
7. Upsert the current `Payment` or `UpiMandate` state.
8. Create or update a `PaymentAttempt` when a payment entity is present.
9. Record checkout outcome correlation when an order ID is available.
10. Commit the transaction and clear the in-process analytics cache.

Unknown event types are still retained in the event stream even if they do not yet update a normalized table.

### Checkout path

The frontend test checkout uses the Razorpay Checkout SDK loaded by `components/payments/razorpaySdk.js`.

1. `POST /api/checkout/order` creates a provider order and returns only the public key and order details.
2. The SDK collects payment details in Razorpay-hosted UI.
3. `POST /api/checkout/verify` verifies the `order_id|payment_id` signature, fetches the provider payment, and stores it using the same persistence path as webhooks.
4. `POST /api/checkout/payment` can synchronize a payment after a failed SDK flow; this path intentionally does not perform checkout signature verification.
5. Checkout telemetry is sent to `/api/webhooks/checkout` or `/api/checkout/events`.

### Mandate rules

Ordinary UPI payments do not automatically become mandates. A mandate is created from a genuine mandate event or from a UPI payment containing a mandate identifier in its notes. This prevents normal UPI transactions from polluting mandate metrics.

## 7. Analytics Logic

`services/analytics.py` calculates all dashboard values from database records. The common success statuses are `success`, `captured`, and `authorized`; failure statuses are `failed` and `attempted`.

`compute_summary()` calculates:

- transaction count and total volume
- success rate
- failed count and amount at risk
- UPI failure rate
- checkout abandonment
- mandate health and mandate failure rate
- recovered amount and recovery rate

Other analytics functions provide failure-reason breakdowns, payment-method distribution, date-bucketed payment series, mandate statistics, and checkout funnel analytics.

Analytics functions use a 20-second in-process TTL cache. Ingestion and recovery writes explicitly clear the cache so subsequent reads see fresh values. Date grouping branches between SQLite date functions and PostgreSQL-compatible expressions.

## 8. Checkout Intelligence

Checkout telemetry is represented by event stages:

```text
checkout_started
payment_method_selected
payment_initiated
otp_started
otp_completed
payment_completed
```

The checkout analytics service counts distinct sessions at each stage and calculates each stage as a percentage of started checkouts. It also derives:

- OTP attempts versus completions
- payment retries
- page reloads, represented by repeated `checkout_started` events for one session
- average checkout duration
- drop-off by payment method
- drop-off by device
- daily drop-off trend

The investigation summary applies deterministic heuristics. For example, incomplete OTPs indicate OTP friction, multiple retries indicate transient provider failures, repeated reloads indicate a display or authorization issue, and conversion below 40% is treated as low.

## 9. Anomaly Detection

Anomaly detection runs when anomalies are requested and can also be invoked by the AI pipeline. It compares the selected period with the immediately preceding period of equal duration.

Detection rules cover:

- payment failure spikes
- payment success-rate drops
- payment-method anomalies
- checkout drop-off spikes
- repeated failure patterns by reason and method

The detector requires a minimum baseline sample. A candidate is only generated when the current and comparison periods contain enough observations. Thresholds include a 1.5x rate change, a minimum 10 percentage-point change for some comparisons, and minimum failure counts.

`detect_with_status()` persists one active anomaly of each type per UTC day. It stores severity, current/baseline metrics, affected transactions, amount at risk, and a deterministic explanation. `POST /api/anomalies/{id}/resolve` marks an active record resolved.

## 10. Recovery Engine

`services/recovery_engine.py` turns failed payments and abandoned checkout sessions into non-executing recommendations via `ensure_candidates()`.

Recommendation logic:

- missing failure reason: escalate for investigation
- repeated failure for the same order/customer: manual review
- decline, bank, insufficient-funds, or invalid-related reason: alternate payment method notification
- other known failures: retry reminder
- abandoned checkout: checkout recovery reminder

Recovery probability is estimated from the failure reason. Risk is based on amount: below ₹2,500 is low, ₹2,500–₹9,999 is medium, and ₹10,000 or more is high.

Supported execution actions are `retry`, `refund`, `notify`, `escalate`, and `ignore`. Before execution, the engine checks:

1. action validity and record state
2. payment status suitability
3. retry count and cooldown
4. refund eligibility and remaining refundable balance
5. configured maximum refund amount
6. high/critical risk restrictions
7. approval requirements for AI actors
8. duplicate successful/pending outcomes within the cooldown window

Retries create a Razorpay payment link. Refunds call the Razorpay refund API and update local refund totals. Notify and escalate currently create local success outcomes only. Every execution creates a `RecoveryOutcome` and `AuditLog`, then clears analytics cache.

## 11. AI Operations Agent

There are two related AI interfaces:

- `POST /api/agent/ask`: conversational agent with tools
- `POST /api/ai-agent/analyze`: structured operational analysis endpoint

The conversational agent can use controlled tools for payment metrics, failed payments, failure breakdown, checkout metrics, mandate metrics, anomalies, and recovery candidates. Tool execution always queries the local database through known service functions; the model cannot issue arbitrary database operations.

When `GROQ_API_KEY` is configured, the agent makes a maximum of two tool-calling rounds against the Groq-compatible API. The system prompt tells the model to answer only from tool results, avoid invented figures, state risk, and recommend an operational action.

When Groq is missing, unavailable, times out, or returns an invalid response, the agent uses `_deterministic_answer()`. That fallback answers common questions about failures, risk, recovery, checkout, mandates, and anomalies directly from database queries. Every non-empty question is stored in `ai_decisions` with answer, tools, model source, summary statistics, and latency.

After relevant payment or checkout processing, background analysis can enrich the operational pipeline without blocking the original ingestion response.

## 12. Reports, Settings, and Notifications

Reports support daily, failure, recovery, UPI, checkout, and AI-operations views. Report values are derived from the same live database services, and daily reports can be persisted for history.

Settings are served by `GET /api/settings` and updated by `PUT /api/settings`. They cover merchant identity, AI enablement, recovery limits, approval behavior, notification preferences, and audit logging. Provider secrets are not returned through the API.

Notifications are synthesized from active anomalies, recovery recommendations, and failed mandates. The current implementation is read-only; there is no backend mark-as-read endpoint.

## 13. Project Structure

```text
backend/
  app/
    main.py                 FastAPI application and router registration
    config.py               environment configuration and provider flags
    database.py             SQLAlchemy engine, sessions, table initialization
    models.py               database entities
    routers/                HTTP endpoint definitions
    services/               business logic and provider integrations
    utils/                  cache, security, dates, formatting, logging
  requirements.txt
  .env.example

frontend/
  src/
    api/                    centralized API client and endpoint helpers
    components/             layout, UI, payment, chart, and agent components
    context/                app-wide route/settings/toast state
    hooks/                  reusable browser and API hooks
    pages/                  dashboard pages
    types/                  display metadata
    utils/                  formatting and date presets
    App.jsx                 route shell and page selection
    main.jsx                React entry point
  package.json
  vite.config.js
```

## 14. Current Limitations

- No authentication or authorization is implemented.
- There are no automated tests, Docker files, or production deployment configuration in the repository.
- There are no database migrations; startup uses `create_all()`.
- The checkout payment-sync endpoint intentionally accepts a payment ID without checkout signature verification.
- Notify and escalate actions do not yet call an email provider or external operations queue.
- Notifications cannot be marked read through the backend.
- Frontend recovery currently focuses on recommendation/status display; execution integration should be treated as a separate hardening task.
- The checked-in SQLite database and log files may contain local operational artifacts and should not be treated as portable seed data.

## 15. Recommended Production Hardening

1. Add authentication, authorization, tenant isolation, and secret management.
2. Add Alembic migrations and remove reliance on `create_all()` for deployed environments.
3. Add webhook replay tests, signature tests, analytics fixtures, recovery policy tests, and AI fallback tests.
4. Move long-running provider and AI calls to an asynchronous job or queue model.
5. Add real notification and escalation integrations.
6. Add structured observability, rate limits, and deployment health checks.
