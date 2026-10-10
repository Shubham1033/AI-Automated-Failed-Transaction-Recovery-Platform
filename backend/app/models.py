from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class FailureCategory(StrEnum):
    AMBIGUOUS = "ambiguous"
    SYSTEMIC = "systemic"
    TEMPORARY_CUSTOMER = "temporary_customer"
    CUSTOMER_ACTIONABLE = "customer_actionable"
    PERMANENT_INSTRUMENT = "permanent_instrument"
    RISK_OR_COMPLIANCE = "risk_or_compliance"


class CaseState(StrEnum):
    DETECTED = "detected"
    RECONCILING = "reconciling"
    DIAGNOSED = "diagnosed"
    WAITING = "waiting"
    PENDING_APPROVAL = "pending_approval"
    ACTIONED = "actioned"
    OBSERVING = "observing"
    RECOVERED = "recovered"
    EXHAUSTED = "exhausted"
    ESCALATED = "escalated"
    STOPPED = "stopped"


class PolicyResult(StrEnum):
    ALLOW = "allow"
    WAIT = "wait"
    APPROVAL = "approval"
    BLOCK = "block"


@dataclass(frozen=True)
class PaymentFacts:
    payment_id: str
    order_id: str | None
    amount_paise: int
    currency: str
    status: str
    method: str | None
    provider: str | None
    customer_name: str
    email: str | None
    contact: str | None
    error_code: str | None
    error_source: str | None
    error_step: str | None
    error_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Classification:
    category: FailureCategory
    code: str
    explanation: str
    requires_reconciliation: bool


@dataclass(frozen=True)
class RecoveryPlan:
    diagnosis: str
    confidence: float
    strategy: str
    delay_minutes: int
    channel: str
    language: str
    reason: str
    requires_human_approval: bool


@dataclass(frozen=True)
class PolicyDecision:
    result: PolicyResult
    reason_code: str
    reason: str
    effective_action: str | None = None

