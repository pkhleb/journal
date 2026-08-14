# Store guide

This folder contains the Pinia stores used by the Vue application.

## Stores

- `auth.js`: manages the JWT token and user session state
- `journal.js`: holds journal entries, inventory, and API interactions
- `counter.js`: example/demo state left in the scaffold and not part of the product flow

## Conventions

- Stores should expose action methods instead of mutating state directly from components
- API-backed actions should coordinate with the shared `apiFetch` helper
- Derived values should remain computed rather than duplicated in component state
