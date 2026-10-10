# Final 3-minute demo

## 0:00–0:25 — Problem
Payment failure does not always mean “message the customer.” Some failures are systemic, some resolve late, and some require customer action. ReviveAI closes the loop while keeping execution bounded.

## 0:25–1:05 — Intelligent restraint
Click **Run judge demo**, open a systemic case, and show the LangGraph trace. Point out `wait_for_incident_resolution` and the absence of a customer email. Open **Rail incidents** and show correlated failure rate and suppressed contacts.

## 1:05–1:50 — Recovery action
Open a customer-actionable case. Show customer context, recovery score, Gemini plan, deterministic policy decision, Hinglish email preview and secure Payment Link. If Test Mode is enabled, complete one Razorpay test payment and refresh: the case becomes `RECOVERED`, pending work is cancelled, and revenue is attributed once.

## 1:50–2:15 — HITL and Promise-to-Pay
Open **Approvals** and demonstrate a high-value case paused for human approval. Approve or reject it and show the audited reviewer event. In a case, record “Salary 2nd ko aayegi, tab payment kar dunga” as Promise-to-Pay and show the scheduled reconciliation state.

## 2:15–2:45 — Measured impact
Open **Batch Lab**. Use 1,000 cases, seed 2026. Explain that the benchmark is synthetic and paired. Show ₹14.67L ReviveAI vs ₹9.49L naive, +54.6% uplift, +₹5.18L incremental recovery, and 293 fewer contacts.

## 2:45–3:00 — Governance
Open **Recovery Ledger** and show integrity verification. Close with: “Gemini decides how to recover. Deterministic policy decides whether it is allowed. Payment truth proves whether money was recovered.”
