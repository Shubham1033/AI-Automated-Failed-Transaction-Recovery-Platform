from __future__ import annotations
from celery import Celery
from .config import settings

celery_app = Celery("revive_ai", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"], timezone="UTC", task_always_eager=settings.celery_eager)

def _service():
    from .factory import create_service
    return create_service()

@celery_app.task(name="revive.reconcile_payment")
def reconcile_payment(case_id: str) -> dict:
    return _service().reconcile_case(case_id)

@celery_app.task(name="revive.execute_recovery")
def execute_recovery(case_id: str) -> dict:
    return _service().resume_case(case_id)

@celery_app.task(name="revive.escalate_case")
def escalate_case(case_id: str) -> dict:
    return _service().escalate_case(case_id, "scheduled_escalation")

def schedule_reconciliation(case_id: str, delay_minutes: int) -> str:
    seconds = max(1, int(delay_minutes * 60 * settings.demo_time_scale))
    result = reconcile_payment.apply_async(args=[case_id], countdown=seconds)
    return result.id


def schedule_promise_check(case_id: str, promised_date: str) -> str:
    # Demo-safe durable follow-up. In production calculate ETA from promised_date; demo time scale keeps it observable.
    seconds = max(2, int(24 * 60 * 60 * settings.demo_time_scale))
    result = reconcile_payment.apply_async(args=[case_id], countdown=seconds)
    return result.id
