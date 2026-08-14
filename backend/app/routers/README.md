# Router module guide

This folder contains the authenticated API endpoints exposed by the FastAPI backend.

## Modules

- `users.py`: registration, login, email verification, and account lookup
- `entries.py`: CRUD for journal entries and exercise ranking endpoints
- `inventory.py`: inventory management and consumption actions

## Route prefixes

- `/api/users/*`
- `/api/entries*`
- `/api/inventory*`
- `/api/exercises/ranked`

## Authentication model

Most routes depend on `auth.get_current_user()`, which validates the JWT and fetches the current user from the database. The service rejects invalid or expired bearer tokens with a 401 error.

## Endpoint notes

- Registration triggers a verification email and creates a user record marked as unverified.
- Login enforces rate limits and account lockout rules.
- `POST /api/entries` can trigger ranking resolution for exercise entries.
- Exercise ranking data is produced by the predictor service and not stored as a direct API response model.
