from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import PaymentFacts, PolicyDecision, PolicyResult, RecoveryPlan


@dataclass(frozen=True)
class PolicyContext:
    payment_captured: bool = False
    opted_out: bool = False
    dispute_open: bool = False
    active_incident: bool = False
    message_count: int = 0
    status_check_count: int = 0
    active_payment_link: bool = False
    timezone: str = "Asia/Kolkata"
    now_hour_override: int | None = 12


def evaluate_policy(
    payment: PaymentFacts, plan: RecoveryPlan, context: PolicyContext
) -> PolicyDecision:
    if context.payment_captured:
        return PolicyDecision(PolicyResult.BLOCK, "already_paid", "Payment is already captured.")
    if context.opted_out:
        return PolicyDecision(PolicyResult.BLOCK, "customer_opted_out", "Customer opted out.")
    if context.dispute_open:
        return PolicyDecision(PolicyResult.APPROVAL, "active_dispute", "Human review required.")
    if context.active_incident:
        return PolicyDecision(
            PolicyResult.WAIT, "active_incident", "Wait for payment-rail recovery."
        )
    if plan.strategy in {"observe", "wait_for_incident_resolution"}:
        if context.status_check_count >= 3:
            return PolicyDecision(
                PolicyResult.APPROVAL, "recheck_limit", "Status recheck limit reached."
            )
        return PolicyDecision(PolicyResult.WAIT, "observation_window", plan.reason, "reconcile")
    if context.message_count >= 2:
        return PolicyDecision(
            PolicyResult.APPROVAL, "message_limit", "Automated contact limit reached."
        )
    if context.active_payment_link and plan.strategy == "send_payment_link":
        return PolicyDecision(
            PolicyResult.ALLOW,
            "reuse_active_link",
            "Reuse the existing active Payment Link.",
            "reuse_payment_link",
        )
    local_hour = (
        context.now_hour_override
        if context.now_hour_override is not None
        else datetime.now(ZoneInfo(context.timezone)).hour
    )
    if plan.channel != "none" and (local_hour >= 21 or local_hour < 8):
        return PolicyDecision(PolicyResult.WAIT, "quiet_hours", "Reschedule outside quiet hours.")
    if plan.requires_human_approval or payment.amount_paise >= 5_000_000:
        return PolicyDecision(
            PolicyResult.APPROVAL, "high_value", "High-value recovery requires approval."
        )
    return PolicyDecision(PolicyResult.ALLOW, "safe_action", "All controls passed.", plan.strategy)

