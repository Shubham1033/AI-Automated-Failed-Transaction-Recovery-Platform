# Sprint 3 Evaluation Method

Each synthetic customer gets one deterministic latent propensity draw. Organic, naive, and ReviveAI strategies are evaluated against the same draw, making the experiment paired and replayable. Strategy probabilities are explicit assumptions, not learned production estimates.

ReviveAI suppresses outreach for provider degradation and late authorization scenarios. Communication is assumed to cost 90 paise per message and orchestration/model allowance is 15 paise per case. These values are demo assumptions and can be configured in a future experiment configuration table.

Primary metrics: recovered value, recovery rate, incremental value vs naive, uplift vs naive, messages avoided, and cost per recovered ₹1,000.
