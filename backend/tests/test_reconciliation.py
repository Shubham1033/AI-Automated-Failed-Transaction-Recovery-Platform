import unittest
from app.database import Database
from app.service import RecoveryService

def timeout_event():
    return {"id":"evt_reconcile","event":"payment.failed","payload":{"payment":{"entity":{"id":"pay_reconcile","order_id":"order_reconcile","amount":499900,"currency":"INR","status":"failed","method":"upi","bank":"UPI","error_code":"GATEWAY_ERROR","error_source":"gateway","error_step":"payment_authorization","error_reason":"timeout","notes":{"customer_name":"Demo"}}}}}

class ReconciliationTests(unittest.TestCase):
    def test_ambiguous_failure_becomes_customer_authorized_recovery_after_recheck(self):
        service=RecoveryService(Database(":memory:"))
        first=service.ingest_event(timeout_event())
        self.assertEqual(first["status"], "wait")
        result=service.reconcile_case(first["case_id"])
        self.assertEqual(result["status"], "actioned")
        self.assertIn("https://", result["payment_link"])
        case=service.get_case(first["case_id"])
        self.assertEqual(case["status_check_count"],1)
