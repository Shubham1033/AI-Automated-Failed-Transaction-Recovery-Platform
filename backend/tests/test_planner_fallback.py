import unittest

from app.classifier import classify_payment
from app.models import PaymentFacts
from app.planner import FallbackRecoveryPlanner


class FailingPlanner:
    def plan(self, payment, classification):
        raise TimeoutError("model unavailable")


class PlannerFallbackTests(unittest.TestCase):
    def test_model_failure_uses_deterministic_plan(self) -> None:
        payment = PaymentFacts(
            payment_id="pay_1",
            order_id="order_1",
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
        plan = FallbackRecoveryPlanner(FailingPlanner()).plan(payment, classify_payment(payment))
        self.assertEqual(plan.strategy, "send_payment_link")
        self.assertGreater(plan.confidence, 0)


if __name__ == "__main__":
    unittest.main()

