import unittest

from app.models import PaymentFacts, PolicyResult, RecoveryPlan
from app.policy import PolicyContext, evaluate_policy


PAYMENT = PaymentFacts(
    payment_id="pay_test",
    order_id="order_test",
    amount_paise=149900,
    currency="INR",
    status="failed",
    method="upi",
    provider="UPI",
    customer_name="Aditi",
    email=None,
    contact=None,
    error_code="BAD_REQUEST_ERROR",
    error_source="bank",
    error_step="payment_authorization",
    error_reason="authentication_failed",
)

PLAN = RecoveryPlan(
    diagnosis="Customer-actionable failure",
    confidence=0.92,
    strategy="send_payment_link",
    delay_minutes=10,
    channel="whatsapp",
    language="hinglish",
    reason="Provide a fresh authorized path.",
    requires_human_approval=False,
)


class PolicyTests(unittest.TestCase):
    def test_captured_payment_is_blocked(self) -> None:
        decision = evaluate_policy(PAYMENT, PLAN, PolicyContext(payment_captured=True))
        self.assertEqual(decision.result, PolicyResult.BLOCK)
        self.assertEqual(decision.reason_code, "already_paid")

    def test_opt_out_is_blocked(self) -> None:
        decision = evaluate_policy(PAYMENT, PLAN, PolicyContext(opted_out=True))
        self.assertEqual(decision.result, PolicyResult.BLOCK)

    def test_message_limit_escalates(self) -> None:
        decision = evaluate_policy(PAYMENT, PLAN, PolicyContext(message_count=2))
        self.assertEqual(decision.result, PolicyResult.APPROVAL)

    def test_safe_low_value_action_is_allowed(self) -> None:
        decision = evaluate_policy(PAYMENT, PLAN, PolicyContext(now_hour_override=12))
        self.assertEqual(decision.result, PolicyResult.ALLOW)


if __name__ == "__main__":
    unittest.main()

