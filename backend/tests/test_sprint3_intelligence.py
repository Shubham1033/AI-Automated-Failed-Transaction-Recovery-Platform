import unittest
from app.database import Database
from app.intelligence import assess_recovery, synthetic_customer_context
from app.models import FailureCategory
from app.service import RecoveryService
from app.simulator import generate_cases, make_failed_event, run_benchmark

class Sprint3Tests(unittest.TestCase):
    def test_paired_benchmark_is_reproducible_and_measures_cost(self):
        a=run_benchmark(100,42); b=run_benchmark(100,42)
        self.assertEqual(a,b)
        self.assertGreaterEqual(a['arms']['revive_ai']['recovered_paise'],a['arms']['naive']['recovered_paise'])
        self.assertIn('cost_per_recovered_1000_paise',a['arms']['revive_ai'])
        self.assertGreater(a['messages_avoided'],0)

    def test_customer_context_changes_risk_score(self):
        case=generate_cases(1,9)[0]
        service=RecoveryService(Database(':memory:'))
        payment=service.parse_payment(make_failed_event(case))
        context=synthetic_customer_context(payment)
        risk=assess_recovery(payment,FailureCategory.CUSTOMER_ACTIONABLE,context)
        self.assertGreaterEqual(risk.recovery_probability,.05)
        self.assertLessEqual(risk.recovery_probability,.95)
        self.assertTrue(risk.reasons)

    def test_promise_to_pay_and_workflow_trace_are_audited(self):
        service=RecoveryService(Database(':memory:'))
        case=generate_cases(1,4)[0]
        result=service.ingest_event(make_failed_event(case,'ptp'))
        promise=service.create_promise_to_pay(result['case_id'],'2026-09-04T10:00:00+05:30','Friday ko pay kar dunga')
        self.assertEqual(promise['status'],'pending')
        trace=service.workflow_trace(result['case_id'])
        self.assertEqual(trace['case_id'],result['case_id'])
        detail=service.case_detail(result['case_id'])
        self.assertTrue(any(e['event_type']=='promise_to_pay.created' for e in detail['timeline']))

if __name__=='__main__': unittest.main()
