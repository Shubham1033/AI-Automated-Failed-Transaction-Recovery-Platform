# Sprint 3 — Recovery Intelligence & Judge Demo

Sprint 3 moves ReviveAI from infrastructure-complete to evaluation-driven product intelligence.

## Added
- Paired, seeded 100-payment benchmark across Organic, Naive Dunning, and ReviveAI arms.
- Scenario-level recovery breakdown, uplift, message restraint, and cost-per-recovered-₹1,000.
- Customer context and explainable recovery-probability scoring.
- Existing payment-rail health monitor is surfaced as the systemic-failure restraint layer.
- LangGraph-compatible workflow trace endpoint showing controlled state-machine progress.
- Promise-to-pay persistence and audited case state transition.
- Live recent-activity feed API and one-click judge-demo endpoint.
- Dashboard recovery score and benchmark uplift display.
- Deterministic/offline defaults remain intact; Razorpay/Gemini/email stay optional adapters.

## Judge demo API
`POST /api/v1/demo/judge` creates a 30-case live operations batch and returns a separate reproducible 100-case benchmark using seed 2026.

## Measurement contract
Synthetic benchmark results are never represented as merchant production outcomes. All probability and messaging-cost assumptions are explicit in `backend/app/simulator.py`.
