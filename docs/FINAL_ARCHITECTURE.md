# Final architecture

```mermaid
flowchart TD
  A[Razorpay / Synthetic Event Stream] --> B[Webhook Verification + Idempotency]
  B --> C[LangGraph StateGraph]
  C --> D[Failure Intelligence]
  D --> E[Rail Health]
  E --> F[Customer Context + Recovery Score]
  F --> G[Gemini Structured Planner]
  G --> H[Policy & Safety Engine]
  H -->|ALLOW| I[Action Executor]
  H -->|WAIT| J[Redis + Celery]
  H -->|REQUIRE APPROVAL| K[HITL Approval Queue]
  J --> C
  K -->|Approve| I
  K -->|Reject| L[Stop]
  I --> M[AWS SES]
  I --> N[Razorpay Payment Link]
  M --> O[Payment Verification]
  N --> O
  O -->|Captured| P[Exactly-once Attribution]
  O -->|Unpaid| C
  P --> Q[Cancel Pending Work]
  Q --> R[Hash-chained Recovery Ledger]
  R --> S[React Command Center]
```

## Trust boundary
The LLM never receives authority to mutate amount, currency, merchant identity, contact caps, approval thresholds or payment state. Structured plans are recommendations; deterministic policy and payment-provider truth remain authoritative.
