# ReviveAI final architecture

```mermaid
flowchart TD
 A[Revenue Event Stream] --> B[FastAPI Webhook + Idempotency]
 B --> C[LangGraph StateGraph]
 C --> D[Failure Intelligence]
 D --> E[Customer Context + Recovery Score]
 E --> F[Gemini Structured Recovery Planner]
 F --> G[Deterministic Policy & Safety Engine]
 G -->|WAIT| H[Redis + Celery]
 G -->|ALLOW| I[Email + Razorpay Payment Link]
 G -->|REVIEW| J[Human Approval]
 H --> K[Payment Reconciliation]
 I --> K
 J --> I
 K -->|Captured| L[Exactly-once Revenue Attribution]
 K -->|Unpaid| C
 L --> M[Hash-chained Recovery Ledger]
 M --> N[React Recovery Command Center]
```

## Safety boundary
Gemini recommends recovery strategy and language. Deterministic code owns amount, currency, payment status, contact caps, approval thresholds, idempotency, execution, stopping and attribution.

## Adapters
- Payment: simulator or Razorpay Test Mode.
- Messaging: simulated email or SMTP email.
- AI: deterministic fallback or Gemini structured output.
