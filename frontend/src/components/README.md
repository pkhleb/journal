# Component guide

This folder contains reusable UI components used by the journal and inventory views.

## Included components

- `Combobox.vue`: searchable selection input used for exercise and food selection
- `EntryCard.vue`: card view for a single journal entry
- `MetricFields.vue`: dynamic metric editor that adapts to entry type

## Design guidance

- Keep components focused on rendering and simple event emission
- Move stateful logic into stores or composables when it is reused
- Expose a small public API for forms rather than binding deeply to internal state
