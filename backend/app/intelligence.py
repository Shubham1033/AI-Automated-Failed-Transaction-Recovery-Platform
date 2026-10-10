from __future__ import annotations
from dataclasses import dataclass, asdict
from .models import FailureCategory, PaymentFacts

@dataclass(frozen=True)
class CustomerContext:
    successful_payments: int
    failed_payments: int
    customer_tenure_days: int
    lifetime_value_paise: int
    preferred_channel: str
    salary_cycle_match: bool

@dataclass(frozen=True)
class RiskAssessment:
    recovery_probability: float
    value_score: float
    urgency_score: float
    segment: str
    reasons: tuple[str, ...]
    def to_dict(self): return asdict(self)

def synthetic_customer_context(payment: PaymentFacts) -> CustomerContext:
    seed = sum(ord(ch) for ch in payment.payment_id)
    successes = 2 + seed % 11
    failures = seed % 3
    tenure = 30 + seed % 700
    ltv = payment.amount_paise * (successes + 1)
    salary_cycle = payment.error_reason == 'insufficient_funds' and seed % 2 == 0
    return CustomerContext(successes, failures, tenure, ltv, 'email', salary_cycle)

def assess_recovery(payment: PaymentFacts, category: FailureCategory, context: CustomerContext) -> RiskAssessment:
    base = {
        FailureCategory.AMBIGUOUS: .70, FailureCategory.SYSTEMIC: .76,
        FailureCategory.TEMPORARY_CUSTOMER: .64, FailureCategory.CUSTOMER_ACTIONABLE: .72,
        FailureCategory.PERMANENT_INSTRUMENT: .50, FailureCategory.RISK_OR_COMPLIANCE: .18,
    }[category]
    history = min(.12, context.successful_payments * .012) - min(.12, context.failed_payments * .04)
    salary = .10 if context.salary_cycle_match else 0
    probability = max(.05, min(.95, base + history + salary))
    value = min(1.0, payment.amount_paise / 5_000_000)
    urgency = min(1.0, .25 + value * .65)
    segment = 'high_value' if value >= .5 else ('loyal' if context.successful_payments >= 8 else 'standard')
    reasons = [f'{context.successful_payments} prior successful payments', f'{category.value} failure']
    if context.salary_cycle_match: reasons.append('salary-cycle timing signal')
    return RiskAssessment(round(probability, 3), round(value, 3), round(urgency, 3), segment, tuple(reasons))
