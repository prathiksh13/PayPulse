# AI Payment Operations Agent

Milestone 1 project: a professional light-mode merchant payment operations dashboard ("PulseOps") with a React + Vite frontend and a FastAPI backend. The frontend reads real data only from the backend — no fake/demo payment data.

## Stack
- **Frontend**: React 19, Vite 6, Recharts, lucide-react (custom hash router — no react-router)
- **Backend**: FastAPI (Razorpay/webhook structure), Python 3.11+

## Requirements
- Node.js 18+ (built and tested on Node 24 / npm 11)
- Python 3.11+

## Run the backend
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Keep it running on port 8000, or use `python .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000`.

Copy `backend/.env.example` to `backend/.env` and add your Razorpay test credentials locally.
Never commit or share the secret key.

## Run the frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```
Other scripts:

| Command            | Purpose                          |
| ------------------ | -------------------------------- |
| `npm run dev`      | Dev server with HMR              |
| `npm run build`    | Production build to `dist/`      |
| `npm run preview`  | Preview the production build     |

In dev, Vite proxies `/api/*` to `http://localhost:8000`, so no CORS config is needed. Override the target with `VITE_PROXY_TARGET`, or point the app at a different backend with `VITE_API_URL` (e.g. `.env` → `VITE_API_URL=https://api.example.org/api`).

## Pages (hash routes)
| Route          | Page                   |
| -------------- | ---------------------- |
| `#/`           | Overview               |
| `#/payments`   | Payments               |
| `#/upi-mandates` | UPI Mandates         |
| `#/checkout`   | Checkout Intelligence  |
| `#/ai-agent`   | AI Agent               |
| `#/anomalies`  | Anomalies              |
| `#/recovery`   | Recovery Actions       |
| `#/reports`    | Reports                |
| `#/settings`   | Settings               |

## Backend API surface
The frontend (`frontend/src/api/index.js`) expects:

- `GET /api/health`
- `GET /api/dashboard/summary` — **live**
- `GET /api/payments`, `GET /api/payments/{id}`
- `GET /api/mandates`, `GET /api/mandates/{id}`
- `GET /api/checkout/analytics`
- `GET /api/anomalies`, `GET /api/anomalies/{id}`
- `GET /api/recovery/actions`, `POST /api/recovery/actions/{id}/execute`, `GET /api/recovery/actions/history`
- `GET /api/reports`
- `GET/PUT /api/settings`
- `GET /api/agent/status`, `GET /api/agent/investigations`, `POST /api/agent/ask`
- `GET /api/notifications`

Only `/api/health` and `/api/dashboard/summary` are currently implemented. Every other endpoint returns 404 and the UI shows an honest "Waiting for payment events" / "No data available" state instead of fabricated numbers — wire the remaining endpoints to populate the dashboard.

## Frontend structure
```
frontend/src/
  api/        client + endpoint functions (single source of API expectations)
  components/ ui primitives, layout, charts, agent widgets, drawers
  context/    AppContext (route, merchant, date range, settings), ToastContext
  hooks/      useApi, useHashRoute, useDebounce, useOnClickOutside, useLocalStorage
  pages/      9 route pages
  utils/      currency/date/percentage formatters, presets
  types/      status/method/severity metadata
```

Settings, merchant selection, and the selected date range persist locally (localStorage `pulseops.*`) until the backend settings API is live.

PostgreSQL is not required for this milestone.