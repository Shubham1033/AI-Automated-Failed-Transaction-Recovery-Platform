from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from .models import Classification, FailureCategory, PaymentFacts, RecoveryPlan


class RecoveryPlanner:
    """Deterministic fallback planner with the same contract as an LLM adapter."""

    def plan(self, payment: PaymentFacts, classification: Classification) -> RecoveryPlan:
        category = classification.category
        if category == FailureCategory.AMBIGUOUS:
            return RecoveryPlan(
                "Ambiguous payment outcome",
                0.99,
                "observe",
                10,
                "none",
                "english",
                "Reconcile current payment truth before contacting the customer.",
                False,
            )
        if category == FailureCategory.SYSTEMIC:
            return RecoveryPlan(
                "Payment rail degradation",
                0.94,
                "wait_for_incident_resolution",
                20,
                "none",
                "english",
                "Avoid unnecessary outreach while the provider is degraded.",
                False,
            )
        if category == FailureCategory.TEMPORARY_CUSTOMER:
            return RecoveryPlan(
                "Temporary customer payment condition",
                0.84,
                "send_payment_link",
                240,
                "email",
                "hinglish",
                "A delayed, low-pressure retry invitation is suitable.",
                payment.amount_paise >= 5_000_000,
            )
        if category == FailureCategory.PERMANENT_INSTRUMENT:
            return RecoveryPlan(
                "Payment instrument needs replacement",
                0.96,
                "suggest_alternate_method",
                0,
                "email",
                "hinglish",
                "Ask the customer to choose UPI, netbanking, or another card.",
                payment.amount_paise >= 5_000_000,
            )
        if category == FailureCategory.RISK_OR_COMPLIANCE:
            return RecoveryPlan(
                "Risk or compliance review",
                0.98,
                "request_human_review",
                0,
                "none",
                "english",
                "Automation is inappropriate for this case.",
                True,
            )
        return RecoveryPlan(
            "Customer-actionable payment failure",
            0.91,
            "send_payment_link",
            10,
            "email",
            "hinglish",
            "Provide a fresh, customer-authorized payment path.",
            payment.amount_paise >= 5_000_000,
        )


class RecoveryPlanOutput(BaseModel):
    diagnosis: str = Field(max_length=160)
    confidence: float = Field(ge=0, le=1)
    strategy: Literal[
        "observe",
        "wait_for_incident_resolution",
        "send_payment_link",
        "suggest_alternate_method",
        "request_human_review",
        "stop",
    ]
    delay_minutes: int = Field(ge=0, le=2880)
    channel: Literal["none", "email"]
    language: Literal["english", "hindi", "hinglish"]
    reason: str = Field(max_length=300)
    requires_human_approval: bool


class GeminiRecoveryPlanner:
    """Gemini structured-output planner. Policy code remains the financial authority."""
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def plan(self, payment: PaymentFacts, classification: Classification) -> RecoveryPlan:
        safe_context = {
            "amount_paise": payment.amount_paise, "currency": payment.currency,
            "method": payment.method, "provider": payment.provider,
            "error_code": payment.error_code, "error_source": payment.error_source,
            "error_step": payment.error_step, "error_reason": payment.error_reason,
            "deterministic_category": str(classification.category),
            "requires_reconciliation": classification.requires_reconciliation,
        }
        prompt = (
            "You are a bounded Indian fintech revenue-recovery planner. Return only the requested schema. "
            "Never change amount/currency/merchant, never initiate an unauthorized charge. "
            "Ambiguous outcomes must be reconciled first; systemic failures wait. "
            "Customer outreach uses email. Prefer Hinglish for customer-actionable Indian consumer cases.\n"
            + json.dumps(safe_context, default=str)
        )
        response = self.client.models.generate_content(
            model=self.model, contents=prompt,
            config={"response_mime_type":"application/json","response_schema":RecoveryPlanOutput},
        )
        output = response.parsed or RecoveryPlanOutput.model_validate_json(response.text)
        data=output.model_dump(); data["channel"]="email" if data["channel"] != "none" else "none"
        return RecoveryPlan(**data)


class FallbackRecoveryPlanner:
    def __init__(self, primary: object, fallback: RecoveryPlanner | None = None):
        self.primary = primary
        self.fallback = fallback or RecoveryPlanner()

    def plan(self, payment: PaymentFacts, classification: Classification) -> RecoveryPlan:
        try:
            return self.primary.plan(payment, classification)  # type: ignore[attr-defined]
        except Exception:
            return self.fallback.plan(payment, classification)


def render_message(payment: PaymentFacts, strategy: str, language: str) -> str:
    amount = payment.amount_paise / 100
    name = payment.customer_name.split()[0] if payment.customer_name else "there"
    if language == "hinglish":
        if strategy == "suggest_alternate_method":
            return (
                f"Hi {name}, aapka ₹{amount:,.2f} payment complete nahi hua. "
                "Aap UPI, netbanking ya kisi doosre card se securely retry kar sakte hain: {{link}}"
            )
        return (
            f"Hi {name}, aapka ₹{amount:,.2f} payment complete nahi hua. "
            "Koi extra charge nahi laga. Jab convenient ho, yahan securely retry karein: {{link}}"
        )
    return (
        f"Hi {name}, your ₹{amount:,.2f} payment was not completed. "
        "No additional charge was made. You can securely retry here: {{link}}"
    )
