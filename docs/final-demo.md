# Judge demo
1. Sign in as merchant operator.
2. Click **Run judge demo**. It seeds 30 live-looking cases and runs a reproducible 1,000-case paired benchmark.
3. Show revenue at risk, recovered revenue, uplift versus naive dunning and messages avoided.
4. Open a case and show the **LangGraph agent trace**, policy decision and hash-chained audit ledger.
5. Show a degraded payment rail where outreach is suppressed.
6. Open a customer-actionable case and show the Hinglish recovery email with a customer-authorized payment link.
7. Create a promise-to-pay date and show the workflow move to waiting.
8. For the live integration, switch `RAZORPAY_USE_API=true`, complete one Test Mode Payment Link, receive `payment.captured`, and show future work cancelled plus exactly-once attribution.

All benchmark numbers are synthetic assumptions and must be presented as simulation results.
