import unittest

from app.database import Database
from app.ledger import RecoveryLedger
from app.models import CaseState, utc_now


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = Database(":memory:")
        now = utc_now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO payments
                (payment_id, amount_paise, currency, status, customer_name, created_at, updated_at)
                VALUES ('pay_1', 10000, 'INR', 'failed', 'Test', ?, ?)
                """,
                (now, now),
            )
            connection.execute(
                """
                INSERT INTO recovery_cases
                (id, payment_id, state, classification, created_at)
                VALUES ('case_1', 'pay_1', ?, 'ambiguous', ?)
                """,
                (CaseState.DETECTED, now),
            )
        self.ledger = RecoveryLedger(self.database)

    def test_chain_is_valid(self) -> None:
        self.ledger.append("case_1", "case.detected", "system", {"value": 1})
        self.ledger.append("case_1", "plan.created", "agent", {"value": 2})
        result = self.ledger.verify("case_1")
        self.assertTrue(result["valid"])
        self.assertEqual(result["event_count"], 2)

    def test_tampering_is_detected(self) -> None:
        self.ledger.append("case_1", "case.detected", "system", {"value": 1})
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE audit_events SET canonical_payload = '{\"value\":999}' WHERE case_id = 'case_1'"
            )
        self.assertFalse(self.ledger.verify("case_1")["valid"])


if __name__ == "__main__":
    unittest.main()

