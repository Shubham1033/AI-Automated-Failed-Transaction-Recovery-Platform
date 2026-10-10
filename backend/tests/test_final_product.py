import unittest
from app.database import Database
from app.service import RecoveryService

class FinalProductTests(unittest.TestCase):
    def setUp(self):
        self.db=Database(":memory:")
        self.service=RecoveryService(self.db)

    def _actionable(self, amount=499900):
        event={"id":f"evt_{amount}","event":"payment.failed","payload":{"payment":{"entity":{"id":f"pay_{amount}","order_id":f"order_{amount}","amount":amount,"currency":"INR","status":"failed","method":"card","bank":"HDFC","email":"demo@example.com","error_code":"BAD_REQUEST_ERROR","error_source":"customer","error_step":"payment_authentication","error_reason":"authentication_failed","notes":{"customer_name":"Demo Customer"}}}}}
        result=self.service.ingest_event(event, signature_verified=True)
        return result["case_id"]

    def test_communication_is_persisted_and_visible(self):
        case_id=self._actionable()
        detail=self.service.case_detail(case_id)
        self.assertTrue(detail["communications"])
        comm=detail["communications"][0]
        self.assertEqual(comm["channel"],"email")
        self.assertIn("₹",comm["body"])
        self.assertTrue(comm["payment_link"])

    def test_global_ledger_verifies(self):
        self._actionable()
        status=self.service.verify_global_ledger()
        self.assertTrue(status["valid"])
        self.assertGreater(status["event_count"],0)

    def test_reject_pending_approval_is_audited(self):
        case_id=self._actionable(8_500_000)
        self.assertEqual(self.service.get_case(case_id)["state"],"pending_approval")
        self.service.reject_case(case_id,"reviewer@revive.local","Too risky")
        self.assertEqual(self.service.get_case(case_id)["state"],"stopped")
        events=self.service.global_ledger()
        self.assertTrue(any(e["event_type"]=="approval.rejected" for e in events))

if __name__=="__main__": unittest.main()
