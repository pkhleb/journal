# Backend tests guide

## Overview

This folder contains the FastAPI integration tests for the application. The suite validates authentication, health checks, and the exercise prediction flow against an isolated PostgreSQL test database.

## Test database setup

The tests use a separate database configuration defined in `backend/tests/conftest.py`, so they do not touch the local development database used for manual testing.

## Run the suite

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://journal_test:testpassword@localhost:5433/journal_test" \
SECRET_KEY="testsecretkey" \
pytest tests/ -v
```

## Notes

- The suite patches email sending to avoid outbound verification emails during automated tests.
- The project uses SQLAlchemy `create_all()` for initial table creation rather than a migration framework.
- Local tests should run against the test database, not the regular development database.
