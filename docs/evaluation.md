# Evaluation Methodology

ReviveAI's demonstration benchmark is synthetic and reproducible.

## Arms

1. **Organic:** No recovery intervention.
2. **Naive:** Immediate identical reminder for every failure.
3. **ReviveAI:** Reconciliation, degradation suppression, categorized intervention, and stopping.

## Scenarios

- Provider degradation
- Late authorization
- Insufficient funds
- Authentication failure
- Expired instrument
- Customer-actionable generic failure

## Metrics

- Gross recovered revenue
- Incremental recovered revenue versus naive
- Recovery conversion
- Messages sent
- Messages avoided
- Cost per recovery
- Unsafe-action rate

## Attribution

Late authorization before an intervention is organic recovery. A captured payment after an executed recovery action is gross/assisted recovery. A payment ID can be attributed only once.

## Limitations

Response probabilities are product assumptions, not learned merchant outcomes. Real causal claims require randomized cohorts or appropriately matched historical data.

