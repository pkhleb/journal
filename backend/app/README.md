# Application package guide

The `backend/app` package contains the core application domain logic for persistence, auth, validation, and recommendation behavior.

## Layout

- `auth.py`: password hashing and bearer token generation/validation
- `database.py`: SQLAlchemy engine, session factory, and shared Base model
- `email.py`: verification token and email sending functions
- `limiter.py`: SlowAPI rate limiter configuration
- `models.py`: ORM data models for users, entries, inventory, and prediction events
- `schemas.py`: Pydantic request/response schemas
- `predictor/`: ranking logic for suggested exercises
- `routers/`: HTTP endpoint definitions

## Data flow

1. The FastAPI app loads the routers in `backend/main.py`.
2. Requests get a database session from `get_db()`.
3. Authenticated routes call `auth.get_current_user()`.
4. Entries and inventory are persisted through SQLAlchemy models.
5. Exercise suggestions are generated via the predictor service and stored as prediction events.

## Development guidance

- Keep authentication and authorization rules in `auth.py`.
- Put SQLAlchemy schema definitions in `models.py`.
- Put request/response validation in `schemas.py`.
- Keep endpoint logic in the router modules instead of embedding it in the main app file.
- Avoid direct database access outside the `database.py` session pattern.
