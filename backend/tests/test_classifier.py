import unittest

from app.classifier import classify_payment
from app.models import FailureCategory, PaymentFacts


def payment(reason: str, code: str = "BAD_REQUEST_ERROR") -> PaymentFacts:
    return PaymentFacts(
        payment_id="pay_test",
        order_id="order_test",
        amount_paise=149900,
        currency="INR",
        status="failed",
        method="upi",
        provider="UPI",
        customer_name="Aditi Sharma",
        email="aditi@example.com",
        contact="+919876543210",
        error_code=code,
        error_source="bank",
        error_step="payment_authorization",
        error_reason=reason,
    )


class ClassifierTests(unittest.TestCase):
    def test_insufficient_funds_is_temporary(self) -> None:
        result = classify_payment(payment("insufficient_funds"))
        self.assertEqual(result.category, FailureCategory.TEMPORARY_CUSTOMER)

    def test_timeout_requires_reconciliation(self) -> None:
        result = classify_payment(payment("timeout", "SERVER_ERROR"))
        self.assertEqual(result.category, FailureCategory.AMBIGUOUS)
        self.assertTrue(result.requires_reconciliation)

    def test_active_incident_overrides_individual_reason(self) -> None:
        result = classify_payment(payment("authentication_failed"), active_incident=True)
        self.assertEqual(result.category, FailureCategory.SYSTEMIC)


if __name__ == "__main__":
    unittest.main()

