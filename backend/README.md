# Backend developer guide

The backend is a FastAPI service that exposes authenticated APIs for journal entries, inventory management, authentication, and exercise ranking.

## Responsibilities

- Authenticate users with JWT-based bearer tokens
- Manage user accounts and email verification flow
- Store journal entries and inventory data in PostgreSQL
- Rank exercise recommendations based on user history
- Expose health and maintenance endpoints for operation

## Runtime stack

- FastAPI
- SQLAlchemy async ORM
- PostgreSQL
- Pydantic validation
- SlowAPI rate limiting
- Resend email integration

## Local development

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

Wait a moment for Postgres to finish booting before starting the backend or running tests; the first connection can fail if the database is still initializing.

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

Wait for the container to report that Postgres is ready before running the suite, or the first connection attempt can fail during startup.

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

## Main entry points

- `main.py`: FastAPI app factory and startup database initialization
- `app/`: domain code, models, ORM, router logic, and predictor
- `tests/`: API and integration tests
- `check_rankings.py`: helper script to print a user's ranked exercises
- `import.py`: import an exported JSON dataset into the database

## API conventions

- Authenticated routes use `Depends(auth.get_current_user)`
- Routers are mounted under `/api`
- Token endpoint: `/api/users/login`
- Health endpoint: `/api/health`

## Test commands

```bash
DATABASE_URL="postgresql+asyncpg://journal_test:testpassword@localhost:5433/journal_test" \
SECRET_KEY="testsecretkey" \
pytest tests/ -v
```

This project configures an async test database in `backend/tests/conftest.py`.

## Deployment notes

The production stack uses `docker-compose.yml` and expects the database container to be reachable via `DATABASE_URL` from the backend service. The app handles table creation automatically during startup.
