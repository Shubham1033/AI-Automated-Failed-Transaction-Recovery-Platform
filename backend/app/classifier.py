from __future__ import annotations

from .models import Classification, FailureCategory, PaymentFacts


AMBIGUOUS = {"network_error", "timeout", "unknown", "payment_pending"}
TEMPORARY = {"insufficient_funds", "balance_insufficient", "bank_declined"}
ACTIONABLE = {"incorrect_pin", "authentication_failed", "payment_failed", "upi_pin_error"}
PERMANENT = {"expired_card", "card_blocked", "mandate_expired", "instrument_not_supported"}
RISK = {"fraud_suspected", "dispute_open", "customer_opted_out"}
SYSTEMIC_CODES = {"gateway_error", "service_unavailable", "provider_down"}


def classify_payment(payment: PaymentFacts, active_incident: bool = False) -> Classification:
    reason = (payment.error_reason or "unknown").lower()
    code = (payment.error_code or "unknown").lower()

    if active_incident or reason in SYSTEMIC_CODES or code == "gateway_error":
        return Classification(
            FailureCategory.SYSTEMIC,
            code,
            "Failures are correlated with a payment-rail incident.",
            True,
        )
    if reason in RISK:
        return Classification(
            FailureCategory.RISK_OR_COMPLIANCE,
            code,
            "The case requires a compliance or human review.",
            False,
        )
    if reason in AMBIGUOUS or code == "unknown":
        return Classification(
            FailureCategory.AMBIGUOUS,
            code,
            "The final payment outcome is not yet reliable.",
            True,
        )
    if reason in PERMANENT:
        return Classification(
            FailureCategory.PERMANENT_INSTRUMENT,
            code,
            "The current payment instrument should be replaced.",
            False,
        )
    if reason in TEMPORARY:
        return Classification(
            FailureCategory.TEMPORARY_CUSTOMER,
            code,
            "The failure may resolve after a respectful delay.",
            False,
        )
    if reason in ACTIONABLE:
        return Classification(
            FailureCategory.CUSTOMER_ACTIONABLE,
            code,
            "The customer can complete a fresh authorized attempt.",
            False,
        )
    return Classification(
        FailureCategory.CUSTOMER_ACTIONABLE,
        code,
        "A fresh customer-authorized payment path is appropriate.",
        False,
    )

