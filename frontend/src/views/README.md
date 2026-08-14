# Views guide

This folder contains the page-level screens that compose the journal app.

## Screens

- `JournalView.vue`: main diary experience for entry creation and editing
- `InventoryView.vue`: inventory dashboard and item consumption flow
- `AnalyticsView.vue`: charts and reporting for activity data
- `LoginView.vue`: authentication screen
- `VerifyEmailView.vue`: email verification page

## Responsibilities

- Each view should focus on a single screen and coordinate with the store layer
- Network calls should be made through the shared API helper or store actions
- Views should keep UI-specific formatting separate from data access logic
