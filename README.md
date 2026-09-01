# AI Payment Operations Agent

PayPulse is a merchant payment-operations dashboard. It combines a React/Vite web application with a FastAPI service that ingests Razorpay events, stores normalized payment data, calculates operational metrics, detects anomalies, recommends recovery actions, and exposes an optional AI operations agent.

The application is designed to be honest about data: dashboard values come from the database and empty databases render empty states rather than fabricated transaction numbers.

For the complete architecture and business-logic walkthrough, see [PROJECT_LOGIC.md](PROJECT_LOGIC.md).

## Technology

- **Frontend:** React 19, Vite 6, Recharts, lucide-react, OGL
- **Backend:** FastAPI, SQLAlchemy 2, Uvicorn, httpx
- **Database:** SQLite by default; PostgreSQL/Supabase is supported
- **Auth:** Supabase Auth (email/password) with role-based access control (RBAC)
- **Payment provider:** Razorpay REST API, Checkout SDK, and signed webhooks
- **AI provider:** Groq-compatible chat-completions API, with a deterministic database-backed fallback
- **Routing:** Custom hash routing; React Router is not used

## Requirements

- Node.js 18+
- Python 3.11+
- Razorpay test credentials for real checkout/webhook integration
- Optional Groq API key for LLM-generated responses

## Quick Start

### 1. Configure the backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env` with local test credentials. The application falls back to `backend/pulseops.db` when `DATABASE_URL` is missing or invalid. Never commit `.env` or provider secrets.

### Authentication (Supabase Auth)

PayPulse uses Supabase Auth for login. See the **Authentication** section below for the two demo accounts, the RBAC matrix, and the one-time Supabase setup you must do in the dashboard.

### 2. Start the backend

```bash
python -m uvicorn app.main:app --reload --port 8000
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`, with interactive documentation at `/docs`.

### 3. Start the frontend

```bash
cd ../frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://localhost:8000` by default. Set `VITE_PROXY_TARGET` to change the proxy or `VITE_API_URL` to use a different API base.

## Frontend Pages

| Hash route | Purpose |
| --- | --- |
| `#/dashboard` | Overview KPIs, trends, methods, failures, and recent activity |
| `#/payments` | Search, filter, inspect, and refund payments; launch test checkout |
| `#/upi-mandates` | Inspect UPI mandate status and activity |
| `#/checkout` | Checkout funnel, drop-offs, device/method signals, and investigations |
| `#/ai-agent` | Agent status, investigations, and operational questions |
| `#/anomalies` | View detected anomalies and their evidence |
| `#/recovery` | Review and update recovery recommendations |
| `#/reports` | Generate operational summaries and report views |
| `#/settings` | Merchant, provider, AI, notifications, and recovery policy settings |

`#/` and `#/landing` show the landing page. The dashboard shell uses `/dashboard` for the Overview page.

## API Groups

All endpoints are under `/api`. Except where noted, endpoints require a `Authorization: Bearer <token>` header (unless they are webhooks, checkout-SDK ingestion, or health).

- Auth: `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `GET /auth/demo-credentials`
- Health: `GET /health` (public)
- Dashboard analytics: `/dashboard/summary`, `/dashboard/failure-breakdown`, `/dashboard/methods`, `/dashboard/mandates`, `/dashboard/series`
- Payments: `GET /payments`, `GET /payments/{id}`, `POST /payments/{id}/refund` (admin)
- Mandates: `/mandates` and the compatibility alias `/upi-mandates`
- Checkout: `/checkout/analytics`, `/checkout/events`, `/checkout/order`, `/checkout/verify`, `/checkout/payment` (ingestion endpoints are public for the merchant SDK/webhooks)
- Checkout intelligence: `/checkout-intelligence/summary`, `/trend`, `/dropoff-reasons`, `/recent`
- Webhooks: `/webhooks/razorpay`, `/webhooks/checkout` (public, signed)
- Anomalies: `GET /anomalies`, `GET /anomalies/{id}`, `POST /anomalies/{id}/resolve`
- Recovery: `/recovery/actions`, `/recovery/actions/history`, `/recovery/actions/{id}/approve` (admin), `/recovery/actions/{id}/execute` (admin), and status updates (admin)
- Reports: `/reports`, `/reports/summary`, `/reports/history`
- Settings: `GET /settings` (auth), `PUT /settings` (admin)
- AI agent: `/agent/status`, `/agent/investigations`, `POST /agent/ask`, `POST /ai-agent/analyze`
- Notifications and cache: `GET /notifications`, `POST /cache/invalidate`

## Authentication & Roles

PayPulse adds multi-user login backed by Supabase Auth with two roles:

| Role | Can do | Recovery approval / execution |
| --- | --- | --- |
| **Admin** | Everything, incl. settings, refunds, recovery approval & execution | Yes |
| **Analyst** | View everything (dashboard, payments, anomalies, reports, checkout, mandates); **view-only** for recovery | No (blocked) |

Sensitive operations (recovery approval, recovery execution, refunds, policy/settings updates) are admin-only on both the API and the UI.

### Demo accounts

Use either demo account (both belong to the demo merchant `demo_merchant_001`). No email confirmation is required.

| Email | Password | Role |
| --- | --- | --- |
| `admin@paypulse.demo` | `PayPulse@123` | Admin |
| `analyst@paypulse.demo` | `PayPulse@123` | Analyst |

You can also copy any credential directly from the login page (a "Demo accounts" panel auto-fills them).

### One-time Supabase setup

1. In the Supabase dashboard, run the SQL from `supabase/schema.sql` (creates `profiles` + `merchants`, RLS policies, the auth trigger, and seeds the demo merchant).
2. Create the two demo users under **Authentication → Users** with the emails above and password `PayPulse@123`. Ensure **Confirm email** is turned off (or confirm them manually).
3. If you created the users via the UI (so the trigger already made their profiles), promote the admin by running:
   `update public.profiles set role='admin' where email='admin@paypulse.demo';`
4. Set these in `backend/.env`:
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY` (public — safe for the frontend), `SUPABASE_SERVICE_ROLE_KEY` (server-only — never expose), `DEMO_MERCHANT_ID=demo_merchant_001`.

> The frontend only ever receives public Supabase config. The service-role key and provider secrets live only in `backend/.env` and are never exposed through the API or committed to Git.

## Useful Commands

| Command | Purpose |
| --- | --- |
| `npm run dev` | Frontend development server with HMR |
| `npm run build` | Production frontend build in `frontend/dist/` |
| `npm run preview` | Serve the production frontend locally |

## Important Notes

- Database tables are created on backend startup. A lightweight, idempotent migration on startup adds the auth/RBAC columns (`merchant_id`, `user_id`, `actor_role`, `approved_by_user_id`, `executed_by_user_id`, `approved_at`) to databases created before this change, preserving existing rows and backfilling the demo merchant.
- Razorpay amounts are received in paise and normalized to rupees before storage.
- Settings, merchant selection, and date range are also persisted in browser localStorage under `pulseops.*`.
- Recovery actions record who approved (`approved_by_user_id`) and who executed (`executed_by_user_id`) them; audit logs record `user_id`, `role`, and `merchant_id` and never store passwords.
- Historical demo data (7-day/30-day trends, anomalies, recovery, checkout, mandates, AI decisions) is seeded once and reused — it is not regenerated randomly on startup.
- `POST /api/checkout/payment` is intended for failed SDK payment synchronization and does not verify a checkout signature.
- `notify` and `escalate` recovery actions currently record local outcomes; external email and operations-queue integrations are not implemented.

