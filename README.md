# Journal

Journal is a full-stack habit and nutrition tracking application. It combines a FastAPI backend, a Vue 3 frontend, and a PostgreSQL database behind Caddy for TLS and reverse proxying. The application lets users log entries, track inventory, and receive exercise suggestions ranked by a lightweight predictor model.

## Project overview

- Backend: FastAPI app serving authenticated JSON APIs
- Frontend: Vue 3 + Vite single-page app
- Database: PostgreSQL 16
- Proxy: Caddy for HTTP/HTTPS routing
- Deployment model: Docker Compose for service orchestration

## Repository layout

- `backend/`: FastAPI service and application logic
- `frontend/`: Vue frontend assets and build config
- `Caddyfile`: reverse proxy and TLS configuration
- `docker-compose.yml`: local and production container orchestration
- `static/`: built frontend output for static serving or fallback deployment
- `history.json`: exported sample data used for import and testing

## Developer information

### Prerequisites

- Python 3.12+
- Node.js 20+ or 22+
- Docker and Docker Compose
- PostgreSQL client tools (optional for local inspection)

# Backend — Local Development Setup

## Prerequisites

- Python 3.12
- Docker (for a local Postgres instance)

## 1. Clone and install dependencies

```bash
git clone https://github.com/pkhleb/journal.git
cd journal/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Start a local Postgres

The app talks to Postgres via `DATABASE_URL` — no local Postgres install needed, just a container:

```bash
docker run --name journal-local-db \
  -e POSTGRES_USER=journal \
  -e POSTGRES_PASSWORD=localdev \
  -e POSTGRES_DB=journal_local \
  -p 5433:5432 \
  -d postgres:16
```

Using port `5433` (not the default `5432`) avoids colliding with any other local Postgres you might have running.

## 3. Environment variables

The app reads these from the environment — there is no `.env` file in the repo (production's lives only on the server, outside version control). Set them inline per-command, or export them in your shell:

| Variable | Local value | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://journal:localdev@localhost:5433/journal_local` | Matches the container from step 2 |
| `SECRET_KEY` | any string, e.g. `local-dev-secret` | Used for JWT signing — doesn't need to match production locally |
| `RESEND_API_KEY` | any placeholder string | Email sending isn't exercised in normal local dev |
| `FRONTEND_URL` | `http://localhost:5173` (or wherever the frontend dev server runs) | Used for links in verification emails |

## 4. Run the backend

```bash
DATABASE_URL="postgresql+asyncpg://journal:localdev@localhost:5433/journal_local" \
SECRET_KEY="local-dev-secret" \
RESEND_API_KEY="placeholder" \
FRONTEND_URL="http://localhost:5173" \
uvicorn main:app --reload --port 8000
```

Tables are created automatically on startup (`app.on_event("startup")` runs `Base.metadata.create_all`) — no separate migration step is needed for a fresh local database.

The API is now live at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

## 5. Running tests

Tests use their own separate database so they never touch the one from step 2. Start it the same way, with credentials matching `tests/conftest.py`:

```bash
docker run --name journal-test-db \
  -e POSTGRES_USER=journal_test \
  -e POSTGRES_PASSWORD=testpassword \
  -e POSTGRES_DB=journal_test \
  -p 5433:5432 \
  -d postgres:16
```

(Note: this uses the same port `5433` as the dev DB above — stop one before starting the other, or change the port mapping if you want both running simultaneously.)

Then run the suite:

```bash
DATABASE_URL="postgresql+asyncpg://journal_test:testpassword@localhost:5433/journal_test" \
SECRET_KEY="testsecretkey" \
pytest tests/ -v
```

This mirrors what CI runs in `.github/workflows/deploy.yml`, minus GitHub Actions' service-container wrapper.

## 6. Optional: working with real data locally

To test against your actual workout/entry history instead of an empty database:

1. Export your data from the live app: `GET /api/export/db` (authenticated), or via `curl` with a bearer token.
2. Run the import script against your local dev database (step 2's DB, not the test one):

```bash
DATABASE_URL="postgresql+asyncpg://journal:localdev@localhost:5433/journal_local" \
SECRET_KEY="local-dev-secret" \
python import.py path/to/export.json
```

This creates a fresh local user (`test@local.dev` by default) and imports your entries/inventory under it — it does not carry over your real password or account.

3. `check_rankings.py` is useful for inspecting the exercise ranker directly against imported data without going through the API:

```bash
DATABASE_URL="postgresql+asyncpg://journal:localdev@localhost:5433/journal_local" \
SECRET_KEY="local-dev-secret" \
python check_rankings.py test@local.dev "Squat"
```

## Notes

- There's no local alembic setup — schema changes are applied via SQLAlchemy's `create_all()`, since the project doesn't currently use migrations (new tables only; no altering of existing columns yet).
- If you also want the frontend running locally against this backend, see `frontend/README.md` (or set `VITE_API_URL` / equivalent to `http://localhost:8000` — check `frontend/src/api.js` for the exact env var name in use).

### Local frontend setup

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

The frontend expects the API at `/api` when served together with the backend, or it can point to a different backend via `VITE_API_URL`.

### Local test setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL="postgresql+asyncpg://journal_test:testpassword@localhost:5433/journal_test" \
SECRET_KEY="testsecretkey" \
pytest tests/ -v
```

### Key developer commands

```bash
# Run backend locally
cd backend && uvicorn main:app --reload

# Run frontend locally
cd frontend && npm run dev

# Build production frontend bundle
cd frontend && npm run build

# Start full stack with Docker Compose
docker compose up --build -d
```

### Versioned environment variables

The application expects the following runtime variables in a deployment environment:

- `POSTGRES_PASSWORD`: PostgreSQL password for the database container
- `SECRET_KEY`: JWT signing secret used by the auth layer
- `RESEND_API_KEY`: API key for transactional email verification
- `FRONTEND_URL`: public base URL for verification links sent by email
- `DATABASE_URL`: backend connection string for the database

## Admin and deployment information

### Production deployment with Docker Compose

1. Ensure you have a host with Docker and Docker Compose installed.
2. Copy this repository to the target server.
3. Set the required environment variables before starting services.
4. Launch the stack:

```bash
docker compose up --build -d
```

This starts:

- PostgreSQL database (`db`)
- backend API (`backend`)
- frontend site (`frontend`)
- Caddy reverse proxy (`caddy`)

### Reverse proxy and TLS

The Caddyfile configures the site at `journal.pkhleb.com` and routes:

- `/api/*` to the backend service on port 8000
- all other requests to the frontend container

This permits a single public entry point without exposing the application containers directly.

### Required environment file example

```env
POSTGRES_PASSWORD=change-me
SECRET_KEY=super-long-random-secret
RESEND_API_KEY=re_xxxxxxxxx
FRONTEND_URL=https://journal.pkhleb.com
```

The backend can also be run with a direct `DATABASE_URL` override if needed outside Docker Compose.

### Operational notes

- User verification emails are sent through Resend and link back to `FRONTEND_URL`.
- JWT tokens expire after 30 days by default.
- Failed login attempts lock the account for 15 minutes after five invalid attempts.
- The predictor stores user-specific weight snapshots and updates them when a chosen exercise resolves a prediction event.

## Security recommendations

- Keep `SECRET_KEY` unique and private.
- Use TLS certificates managed by Caddy in production.
- Do not commit real API keys or database credentials to source control.
- Restrict direct database access to trusted admins only.

## Further reading

- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)
- [backend/app/README.md](backend/app/README.md)
- [backend/app/predictor/README.md](backend/app/predictor/README.md)
