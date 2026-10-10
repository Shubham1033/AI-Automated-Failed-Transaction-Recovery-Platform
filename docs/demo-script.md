# Three-Minute Demo Script

## 0:00–0:25 — Problem

“A payment failure may be late authorization, provider degradation, insufficient funds, or a customer-actionable error. Naive dunning treats every failure the same.”

## 0:25–0:55 — Batch lab

Generate the 100-case seeded benchmark and show:

- Organic recovery
- Naive dunning
- ReviveAI recovery
- Incremental recovered revenue
- Messages avoided

State clearly that the benchmark is synthetic.

## 0:55–1:20 — Intelligent restraint

Show an open payment-rail incident. Explain that ReviveAI suppresses individual messages and schedules reconciliation instead.

## 1:20–2:15 — Live recovery

1. Submit `data/fixtures/payment_failed.json`.
2. Open the newly created case.
3. Show deterministic classification.
4. Show the structured planner recommendation.
5. Show the policy decision.
6. Open the generated Razorpay Test Mode Payment Link.
7. Show the Hinglish customer message.

## 2:15–2:40 — Verify and stop

Submit `data/fixtures/payment_captured.json`. Show that the case becomes recovered, pending work is cancelled, and the amount is attributed exactly once.

## 2:40–3:00 — Trust

Open the decision timeline and show `Ledger integrity verified`.

Close with:

> ReviveAI recovered more while contacting fewer customers, and every action and rupee is traceable.

