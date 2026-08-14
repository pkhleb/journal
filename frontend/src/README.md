# Frontend source guide

This folder contains the Vue application code. It is organized into pages, shared utilities, state, and reusable components.

## Key areas

- `views/`: Route-level screens such as journal, inventory, analytics, and login
- `stores/`: Pinia state stores, including auth and journal state
- `components/`: Reusable UI pieces such as entry cards and metric inputs
- `composables/`: Shared behavior hooks for row editing or data shaping
- `router/`: Route registration and auth guard logic
- `api.js`: Helper that injects the bearer token into API requests

## Local patterns

- Authenticated routes redirect to `/login` when there is no saved token
- API requests use a single shared helper to keep authorization and error handling consistent
- State is centralized in Pinia stores rather than spread across components
