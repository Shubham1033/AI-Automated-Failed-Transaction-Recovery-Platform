import unittest

from app.database import Database
from app.service import RecoveryService


def event(event_id: str, status: str, reason: str = "authentication_failed") -> dict:
    return {
        "id": event_id,
        "event": f"payment.{status}",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_flow_1",
                    "order_id": "order_flow_1",
                    "amount": 149900,
                    "currency": "INR",
                    "status": status,
                    "method": "upi",
                    "bank": "UPI",
                    "email": "aditi@example.com",
                    "contact": "+919876543210",
                    "error_code": "BAD_REQUEST_ERROR" if status == "failed" else None,
                    "error_source": "bank" if status == "failed" else None,
                    "error_step": "payment_authorization" if status == "failed" else None,
                    "error_reason": reason if status == "failed" else None,
                    "notes": {"customer_name": "Aditi Sharma"},
                }
            }
        },
    }


class RecoveryFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = Database(":memory:")
        self.service = RecoveryService(self.database)

    def test_failed_to_recovered_closed_loop(self) -> None:
        failed = self.service.ingest_event(event("evt_failed", "failed"))
        self.assertEqual(failed["status"], "actioned")
        self.assertIn("https://", failed["payment_link"])
        recovered = self.service.ingest_event(event("evt_captured", "captured"))
        self.assertEqual(recovered["status"], "recovered")
        detail = self.service.case_detail(failed["case_id"])
        self.assertEqual(detail["case"]["state"], "recovered")
        self.assertTrue(detail["ledger"]["valid"])
        self.assertEqual(len(detail["actions"]), 1)

    def test_duplicate_webhook_is_idempotent(self) -> None:
        payload = event("evt_duplicate", "failed")
        first = self.service.ingest_event(payload)
        second = self.service.ingest_event(payload)
        self.assertEqual(first["status"], "actioned")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(len(self.service.list_cases()), 1)

    def test_late_authorization_is_organic_and_stops(self) -> None:
        failed = self.service.ingest_event(event("evt_timeout", "failed", "timeout"))
        self.assertEqual(failed["status"], "wait")
        recovered = self.service.ingest_event(event("evt_timeout_captured", "captured"))
        self.assertEqual(recovered["attribution_type"], "organic_recovery")
        self.assertEqual(self.service.get_case(failed["case_id"])["state"], "recovered")


if __name__ == "__main__":
    unittest.main()

