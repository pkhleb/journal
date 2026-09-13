# Journal

A self-hosted full-stack journaling and habit-tracking application with a **production personalized exercise-ranking system**.

The project is primarily an exploration of the ML engineering lifecycle: behavioral feature engineering, temporal validation, online inference, user-feedback collection, online personalization, and containerized deployment.

## ML System

The exercise recommender predicts which exercise a user is most likely to perform next.

**Pipeline**

```text
Exercise History
      ↓
Feature Aggregation
      ↓
Candidate Generation
      ↓
Weighted Ranking
      ↓
Prediction Logging
      ↓
Observed User Choice
      ↓
Online Weight Update
```

The ranker uses behavioral signals including:

* exercise-to-exercise transition probabilities
* workout session phase
* weekday behavior
* exercise position
* recency

Predictions and outcomes are persisted, allowing production behavior to feed back into per-user model weights.

### Offline Evaluation

The repository includes a walk-forward evaluation framework designed to avoid temporal leakage.

Experiments support:

* chronological train/test splits
* Top-1 and Top-3 accuracy
* Mean Reciprocal Rank (MRR)
* feature ablation
* hyperparameter sweeps
* evaluation of online weight updates

This provides an offline approximation of how the model would have behaved as historical events arrived sequentially.

## Engineering Stack

**ML / Data:** Python, NumPy, Pandas, custom learning-to-rank pipeline
**Backend:** FastAPI, SQLAlchemy, PostgreSQL
**Frontend:** Vue 3, Pinia, Vite
**Infrastructure:** Docker, Docker Compose, GitHub Actions, GHCR, Caddy

GitHub Actions runs backend integration tests against PostgreSQL, builds and publishes the application container, and deploys the production service.

## Local Setup

### 1. Clone

```bash
git clone https://github.com/pkhleb/journal.git
cd journal
```

### 2. Start PostgreSQL

```bash
docker run --name journal-local-db \
  -e POSTGRES_USER=journal \
  -e POSTGRES_PASSWORD=localdev \
  -e POSTGRES_DB=journal_local \
  -p 5433:5432 \
  -d postgres:16
```

### 3. Run the Backend

Requires Python 3.12+.

```bash
cd backend

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

DATABASE_URL="postgresql+asyncpg://journal:localdev@localhost:5433/journal_local" \
SECRET_KEY="local-dev-secret" \
RESEND_API_KEY="placeholder" \
FRONTEND_URL="http://localhost:5173" \
uvicorn main:app --reload --port 8000
```

API documentation is available at:

```text
http://localhost:8000/docs
```

### 4. Run the Frontend

Requires Node.js 20+.

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend
pytest tests/ -v
```

## Deployment

The complete application can also be run with Docker Compose:

```bash
docker compose up --build -d
```

Production consists of:

```text
Caddy
 ├── Vue frontend
 └── FastAPI backend
          │
      PostgreSQL
```

Caddy provides TLS termination and reverse proxying, while the application services run as containers behind a single public endpoint.

## Repository Structure

```text
backend/
  app/
    predictor/       # Online ranking and feature pipeline
  experiments/       # Walk-forward evaluation and ML experiments
  tests/

frontend/            # Vue application
.github/workflows/   # CI/CD
docker-compose.yml
Caddyfile
```

For additional implementation details, see the READMEs under `backend/`, `frontend/`, and `backend/app/predictor/`.
