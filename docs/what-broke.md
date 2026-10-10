# What Broke

## Duplicate actions during webhook replay

### Symptom

Replaying a failed-payment event could create a second recovery attempt if event processing relied only on an application-level lookup.

### Root cause

Payment webhooks are at-least-once notifications. Two workers can both observe “not processed” before either writes.

### Fix

- Unique event key at the database layer
- Payload hash for events without provider IDs
- Deterministic action idempotency keys
- One-active-Payment-Link partial unique index
- Transactional state changes
- Terminal captured-payment handling

### Regression proof

`test_duplicate_webhook_is_idempotent` sends the same payload twice and asserts that the second event is marked duplicate and only one case exists.

