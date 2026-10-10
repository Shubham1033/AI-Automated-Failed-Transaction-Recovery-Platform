import tempfile, unittest
from app.database import Database
from app.service import RecoveryService
from app.simulator import generate_cases, make_failed_event, run_benchmark

class Sprint4Tests(unittest.TestCase):
    def test_execution_records_langgraph_trace(self):
        with tempfile.NamedTemporaryFile(suffix='.db') as f:
            service=RecoveryService(Database("sqlite:///"+f.name))
            event=make_failed_event(generate_cases(30,17)[-1], 's4')
            result=service.ingest_event(event)
            detail=service.case_detail(result['case_id'])
            graph=[e for e in detail['timeline'] if e['event_type']=='graph.executed']
            self.assertTrue(graph)
            self.assertEqual(detail['workflow']['engine'],'langgraph-stategraph')
            self.assertTrue(any(s['step']=='policy_guard' for s in detail['workflow']['steps']))
    def test_large_benchmark_is_reproducible(self):
        a=run_benchmark(1000,2026); b=run_benchmark(1000,2026)
        self.assertEqual(a,b); self.assertEqual(a['case_count'],1000)
        self.assertGreater(a['incremental_vs_naive_paise'],0)
        self.assertGreater(a['messages_avoided'],0)
if __name__=='__main__': unittest.main()
