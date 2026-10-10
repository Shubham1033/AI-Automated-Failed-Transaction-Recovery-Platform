# Threat Model

## Protected assets

- Payment amount, currency, order, and merchant identity
- Webhook authenticity and payment truth
- Customer contact preferences and personally identifiable information
- Recovery actions and approval records
- Revenue attribution and audit integrity

## Principal threats and controls

| Threat | Control |
|---|---|
| Forged webhook | HMAC verification over exact raw bytes |
| Replay/duplicate delivery | Unique event keys and payload hashes |
| Duplicate Payment Links | Idempotency key and unique active-link index |
| Model changes amount/currency | Financial fields come only from verified payment facts |
| Post-payment outreach | Captured is terminal and pending actions are cancelled |
| Audit modification | Per-case hash chain and integrity verifier |
| Excessive contact | Separate message, call, and status-check caps |
| Provider outage spam | Rolling rail-health incident suppresses outreach |
| Secret leakage | Environment variables, masked logs, secret scanning |
| Race between workers | Transactions, unique constraints, and case versions |

## Trust boundaries

1. Razorpay to webhook endpoint
2. API to persistence layer
3. Recovery planner to deterministic policy engine
4. Policy engine to external action executor
5. Operator to approval/stop endpoints

The LLM is treated as an untrusted recommendation source.

