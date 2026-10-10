from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from .classifier import classify_payment
from .database import Database, json_dumps
from .incidents import RailHealthMonitor
from .ledger import RecoveryLedger
from .models import CaseState, PaymentFacts, PolicyResult, utc_now
from .planner import RecoveryPlanner, render_message
from .policy import PolicyContext, evaluate_policy
from .razorpay import PaymentLinkGateway, PaymentStatusGateway
from .messaging import MessagingGateway
from .intelligence import synthetic_customer_context, assess_recovery
from .orchestrator import workflow_trace
from .recovery_graph import RecoveryGraph


class RecoveryService:
    def __init__(
        self,
        database: Database,
        planner: RecoveryPlanner | None = None,
        payment_links: PaymentLinkGateway | None = None,
        payment_status: PaymentStatusGateway | None = None,
        messaging: MessagingGateway | None = None,
    ):
        self.database = database
        self.ledger = RecoveryLedger(database)
        self.monitor = RailHealthMonitor(database)
        self.planner = planner or RecoveryPlanner()
        self.payment_links = payment_links or PaymentLinkGateway()
        self.payment_status = payment_status or PaymentStatusGateway()
        self.messaging = messaging or MessagingGateway()
        self.recovery_graph = RecoveryGraph(self.planner)

    @staticmethod
    def parse_payment(payload: dict[str, Any]) -> PaymentFacts:
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        if not entity and "payment_link" in payload.get("payload", {}):
            link_entity = payload["payload"]["payment_link"]["entity"]
            entity = {
                "id": f"pay_{link_entity.get('id')}",
                "order_id": link_entity.get("order_id"),
                "amount": link_entity.get("amount_paid") or link_entity.get("amount"),
                "currency": link_entity.get("currency", "INR"),
                "status": "captured" if link_entity.get("status") == "paid" else link_entity.get("status"),
                "notes": link_entity.get("notes"),
            }
        notes = entity.get("notes") or {}
        provider = entity.get("bank") or entity.get("wallet") or notes.get("provider")
        return PaymentFacts(
            payment_id=str(entity.get("id") or f"pay_missing_{uuid.uuid4().hex[:8]}"),
            order_id=entity.get("order_id"),
            amount_paise=int(entity.get("amount") or 0),
            currency=str(entity.get("currency") or "INR"),
            status=str(entity.get("status") or "unknown"),
            method=entity.get("method"),
            provider=provider,
            customer_name=str(notes.get("customer_name") or "Customer"),
            email=entity.get("email"),
            contact=entity.get("contact"),
            error_code=entity.get("error_code"),
            error_source=entity.get("error_source"),
            error_step=entity.get("error_step"),
            error_reason=entity.get("error_reason"),
        )

    def ingest_event(
        self,
        payload: dict[str, Any],
        raw_body: bytes | None = None,
        signature_verified: bool = True,
    ) -> dict[str, Any]:
        event_type = str(payload.get("event") or "unknown")
        raw = raw_body or json_dumps(payload).encode()
        payload_hash = hashlib.sha256(raw).hexdigest()
        event_key = str(payload.get("id") or f"{event_type}:{payload_hash}")
        try:
            with self.database.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO webhook_events
                    (event_key, event_type, payload_hash, raw_payload, signature_verified, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_key,
                        event_type,
                        payload_hash,
                        raw.decode("utf-8"),
                        bool(signature_verified),
                        utc_now(),
                    ),
                )
        except Exception as exc:
            if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
                return {"status": "duplicate", "event_key": event_key}
            raise

        payment = self.parse_payment(payload)
        self._upsert_payment(payment)
        if event_type in {"payment.captured", "order.paid"} or payment.status == "captured":
            return self._handle_captured(payment)
        if event_type == "payment.failed" or payment.status == "failed":
            return self._handle_failed(payment)
        return {"status": "accepted", "event_type": event_type, "payment_id": payment.payment_id}

    def _upsert_payment(self, payment: PaymentFacts) -> None:
        now = utc_now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO payments
                (payment_id, order_id, amount_paise, currency, status, method, provider,
                 customer_name, email, contact, error_code, error_source, error_step,
                 error_reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(payment_id) DO UPDATE SET
                  status = excluded.status,
                  error_code = excluded.error_code,
                  error_source = excluded.error_source,
                  error_step = excluded.error_step,
                  error_reason = excluded.error_reason,
                  updated_at = excluded.updated_at
                """,
                (
                    payment.payment_id,
                    payment.order_id,
                    payment.amount_paise,
                    payment.currency,
                    payment.status,
                    payment.method,
                    payment.provider,
                    payment.customer_name,
                    payment.email,
                    payment.contact,
                    payment.error_code,
                    payment.error_source,
                    payment.error_step,
                    payment.error_reason,
                    now,
                    now,
                ),
            )

    def _handle_failed(self, payment: PaymentFacts) -> dict[str, Any]:
        incident = self.monitor.evaluate(payment.provider, payment.method)
        active_incident = bool(incident or self.monitor.active_incident(payment.provider))
        classification = classify_payment(payment, active_incident=active_incident)
        case = self.database.query_one(
            "SELECT * FROM recovery_cases WHERE payment_id = ?", (payment.payment_id,)
        )
        if not case:
            case_id = f"case_{uuid.uuid4().hex[:14]}"
            now = utc_now()
            with self.database.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO recovery_cases
                    (id, payment_id, state, classification, risk_score, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (case_id, payment.payment_id, CaseState.DETECTED, classification.category, 0.7, now),
                )
            self.ledger.append(
                case_id,
                "case.detected",
                "system",
                {"payment": payment.to_dict(), "classification": classification.category},
            )
        else:
            case_id = case["id"]
            if case["state"] == CaseState.RECOVERED:
                return {"status": "already_recovered", "case_id": case_id}

        case = self.get_case(case_id)
        graph_result = self.recovery_graph.invoke(payment, active_incident, case)
        classification = graph_result["classification"]
        customer_context = graph_result["customer_context"]
        risk = graph_result["risk"]
        plan = graph_result["plan"]
        decision = graph_result["decision"]
        with self.database.transaction() as connection:
            connection.execute("UPDATE recovery_cases SET risk_score = ? WHERE id = ?", (risk.recovery_probability, case_id))
        self.ledger.append(case_id,"graph.executed","langgraph",{"nodes":graph_result.get("trace",[])})
        self.ledger.append(
            case_id,
            "plan.evaluated",
            "agent",
            {
                "classification": classification.category,
                "customer_context": customer_context.__dict__,
                "risk_assessment": risk.to_dict(),
                "plan": plan.__dict__,
                "policy": {
                    "result": decision.result,
                    "reason_code": decision.reason_code,
                    "reason": decision.reason,
                },
            },
        )
        with self.database.transaction() as connection:
            target_state = {
                PolicyResult.WAIT: CaseState.WAITING,
                PolicyResult.APPROVAL: CaseState.PENDING_APPROVAL,
                PolicyResult.BLOCK: CaseState.STOPPED,
                PolicyResult.ALLOW: CaseState.DIAGNOSED,
            }[decision.result]
            next_action = (
                (datetime.now(UTC) + timedelta(minutes=plan.delay_minutes)).isoformat()
                if decision.result == PolicyResult.WAIT
                else None
            )
            connection.execute(
                """
                UPDATE recovery_cases
                SET state = ?, classification = ?, current_strategy = ?,
                    next_action_at = ?, version = version + 1
                WHERE id = ?
                """,
                (target_state, classification.category, plan.strategy, next_action, case_id),
            )

        if decision.result == PolicyResult.WAIT:
            try:
                from .tasks import schedule_reconciliation
                task_id = schedule_reconciliation(case_id, max(1, plan.delay_minutes))
                current_version = int(self.get_case(case_id)["version"])
                with self.database.transaction() as connection:
                    action_id = self._record_scheduled_reconciliation(connection, case_id, task_id, plan.delay_minutes, current_version)
                self.ledger.append(case_id, "reconciliation.scheduled", "system", {"task_id": task_id, "delay_minutes": plan.delay_minutes})
            except Exception as exc:
                # The case remains WAITING even if Redis is temporarily unavailable; reconciliation can be triggered manually.
                self.ledger.append(case_id, "reconciliation.schedule_failed", "system", {"error": type(exc).__name__})
        if decision.result == PolicyResult.ALLOW:
            return self._execute_allowed_action(case_id, payment, plan, decision.reason_code)
        if decision.result == PolicyResult.APPROVAL:
            action_id = self._record_action(
                case_id,
                plan.strategy,
                plan.__dict__,
                decision.result,
                "pending",
                "pending_approval",
            )
            return {"status": "pending_approval", "case_id": case_id, "action_id": action_id}
        return {"status": decision.result, "case_id": case_id, "reason": decision.reason_code}

    def _record_action(
        self,
        case_id: str,
        action_type: str,
        payload: dict[str, Any],
        policy_result: str,
        approval_status: str,
        execution_status: str,
    ) -> str:
        action_id = f"act_{uuid.uuid4().hex[:14]}"
        idempotency_key = hashlib.sha256(
            f"{case_id}:{action_type}:{self.get_case(case_id)['version']}".encode()
        ).hexdigest()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO recovery_actions
                (id, case_id, action_type, idempotency_key, proposed_payload,
                 policy_result, approval_status, execution_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    case_id,
                    action_type,
                    idempotency_key,
                    json_dumps(payload),
                    str(policy_result),
                    approval_status,
                    execution_status,
                    utc_now(),
                ),
            )
            row = connection.execute(
                "SELECT id FROM recovery_actions WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
        return str(row["id"])

    def _execute_allowed_action(
        self, case_id: str, payment: PaymentFacts, plan: Any, reason_code: str
    ) -> dict[str, Any]:
        if plan.strategy not in {"send_payment_link", "suggest_alternate_method"}:
            return {"status": "waiting", "case_id": case_id}
        case = self.get_case(case_id)
        existing = self.database.query_one(
            "SELECT * FROM payment_links WHERE case_id = ? AND status = 'created'", (case_id,)
        )
        if existing:
            link = existing
        else:
            created = self.payment_links.create(case_id, payment.amount_paise, payment.currency)
            link_id = f"link_{uuid.uuid4().hex[:14]}"
            with self.database.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO payment_links
                    (id, case_id, provider_link_id, reference_id, amount_paise,
                     currency, status, short_url, expires_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'created', ?, ?, ?)
                    """,
                    (
                        link_id,
                        case_id,
                        created.provider_link_id,
                        created.reference_id,
                        payment.amount_paise,
                        payment.currency,
                        created.short_url,
                        created.expires_at,
                        utc_now(),
                    ),
                )
                connection.execute(
                    "UPDATE recovery_cases SET active_payment_link_id = ? WHERE id = ?",
                    (link_id, case_id),
                )
            link = self.database.query_one("SELECT * FROM payment_links WHERE id = ?", (link_id,))

        message = render_message(payment, plan.strategy, plan.language).replace(
            "{{link}}", str(link["short_url"])
        )
        recipient = payment.email or "demo@example.com"
        subject = f"Complete your {payment.currency} payment securely"
        message_result = self.messaging.send_email(recipient, subject, message)
        communication_id = f"comm_{uuid.uuid4().hex[:14]}"
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO recovery_communications
                (id,case_id,channel,provider,recipient,subject,body,language,status,provider_message_id,payment_link,created_at,sent_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (communication_id, case_id, "email", getattr(message_result, "provider", "simulated"), recipient, subject, message, plan.language, message_result.status, message_result.provider_message_id, str(link["short_url"]), utc_now(), utc_now()),
            )
        action_id = self._record_action(
            case_id,
            plan.strategy,
            {"message": message, "link_id": link["id"], "policy_reason": reason_code, "provider_message_id": message_result.provider_message_id},
            PolicyResult.ALLOW,
            "not_required",
            "executed",
        )
        now = utc_now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE recovery_actions SET executed_at = ? WHERE id = ?
                """,
                (now, action_id),
            )
            connection.execute(
                """
                UPDATE recovery_cases
                SET state = ?, message_count = message_count + 1,
                    version = version + 1
                WHERE id = ? AND state != ?
                """,
                (CaseState.OBSERVING, case_id, CaseState.RECOVERED),
            )
        self.ledger.append(
            case_id,
            "action.executed",
            "system",
            {"action_id": action_id, "message": message, "link_id": link["id"], "provider_message_id": message_result.provider_message_id, "communication_id": communication_id},
        )
        return {
            "status": "actioned",
            "case_id": case_id,
            "action_id": action_id,
            "payment_link": link["short_url"],
            "message": message,
        }

    def _record_scheduled_reconciliation(self, connection: Any, case_id: str, task_id: str, delay_minutes: int, version: int) -> str:
        action_id = f"act_{uuid.uuid4().hex[:14]}"
        key = hashlib.sha256(f"{case_id}:reconcile:{version}".encode()).hexdigest()
        connection.execute("""INSERT INTO recovery_actions
            (id,case_id,action_type,idempotency_key,proposed_payload,policy_result,approval_status,execution_status,scheduled_at,celery_task_id,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING""",
            (action_id,case_id,"reconcile_payment",key,json_dumps({"delay_minutes":delay_minutes}),"wait","not_required","scheduled",(datetime.now(UTC)+timedelta(minutes=delay_minutes)).isoformat(),task_id,utc_now()))
        return action_id

    def reconcile_case(self, case_id: str) -> dict[str, Any]:
        case = self.get_case(case_id)
        if case["state"] in {CaseState.RECOVERED, CaseState.STOPPED, CaseState.EXHAUSTED}:
            return {"status": "terminal", "case_id": case_id, "state": case["state"]}
        payment_row = self.database.query_one("SELECT * FROM payments WHERE payment_id = ?", (case["payment_id"],))
        payment = self._payment_from_row(payment_row)

        # 1. Check if an active payment link exists and has been paid on Razorpay
        link_row = self.database.query_one(
            "SELECT * FROM payment_links WHERE case_id = ? AND status = 'created' ORDER BY created_at DESC LIMIT 1",
            (case_id,),
        )
        if link_row and hasattr(self.payment_links, "fetch"):
            link_info = self.payment_links.fetch(link_row["provider_link_id"])
            if link_info and link_info.get("status") == "paid":
                payments = link_info.get("payments") or []
                paid_payment_id = payments[0]["payment_id"] if payments else f"pay_recovered_{link_row['provider_link_id']}"
                recovered_amount = link_info.get("amount_paid") or payment.amount_paise
                captured = PaymentFacts(
                    payment_id=paid_payment_id,
                    order_id=link_info.get("order_id") or payment.order_id,
                    amount_paise=int(recovered_amount),
                    currency=payment.currency,
                    status="captured",
                    method=payments[0].get("method") if payments else payment.method,
                    provider=payment.provider,
                    customer_name=payment.customer_name,
                    email=payment.email,
                    contact=payment.contact,
                    error_code=None,
                    error_source=None,
                    error_step=None,
                    error_reason=None,
                )
                self._upsert_payment(captured)
                return self._handle_captured(captured, target_case_id=case_id)

        # 2. Check original payment status
        remote = self.payment_status.fetch(payment.payment_id)
        with self.database.transaction() as connection:
            connection.execute("UPDATE recovery_cases SET status_check_count=status_check_count+1, version=version+1 WHERE id=?", (case_id,))
            connection.execute("UPDATE recovery_actions SET execution_status='executed', executed_at=? WHERE case_id=? AND action_type='reconcile_payment' AND execution_status='scheduled'", (utc_now(),case_id))
        if remote and remote.status == "captured":
            captured = PaymentFacts(**{**payment.to_dict(), "status":"captured", "error_code":None, "error_source":None, "error_step":None, "error_reason":None})
            self._upsert_payment(captured)
            return self._handle_captured(captured, target_case_id=case_id)
        if payment.status == "captured":
            return self._handle_captured(payment, target_case_id=case_id)
        self.ledger.append(case_id, "payment.reconciled", "system", {"status": remote.status if remote else payment.status})
        return self.resume_case(case_id)

    def resume_case(self, case_id: str) -> dict[str, Any]:
        case=self.get_case(case_id)
        payment=self._payment_from_row(self.database.query_one("SELECT * FROM payments WHERE payment_id = ?", (case["payment_id"],)))
        # Re-enter deterministic planning after the observation window. Ambiguous failures become actionable after reconciliation.
        classification=classify_payment(payment, active_incident=bool(self.monitor.active_incident(payment.provider)))
        plan=self.planner.plan(payment, classification)
        if classification.requires_reconciliation and int(case["status_check_count"]) > 0:
            from dataclasses import replace
            plan=replace(plan, strategy="send_payment_link", delay_minutes=0, reason="Reconciled as still unpaid; customer-authorized recovery is now safe")
        context=PolicyContext(payment_captured=False, active_incident=False, message_count=int(case["message_count"]), status_check_count=int(case["status_check_count"]), active_payment_link=bool(case["active_payment_link_id"]))
        decision=evaluate_policy(payment, plan, context)
        if decision.result == PolicyResult.ALLOW:
            return self._execute_allowed_action(case_id,payment,plan,decision.reason_code)
        return {"status":str(decision.result),"case_id":case_id,"reason":decision.reason_code}

    def escalate_case(self, case_id: str, reason: str) -> dict[str, Any]:
        self.get_case(case_id)
        with self.database.transaction() as connection:
            connection.execute("UPDATE recovery_cases SET state=?, version=version+1 WHERE id=?", (CaseState.ESCALATED,case_id))
        self.ledger.append(case_id,"case.escalated","system",{"reason":reason})
        return {"status":"escalated","case_id":case_id}

    def approve_case(self, case_id: str, reviewer: str = "reviewer") -> dict[str, Any]:
        case = self.get_case(case_id)
        payment = self._payment_from_row(
            self.database.query_one("SELECT * FROM payments WHERE payment_id = ?", (case["payment_id"],))
        )
        classification = classify_payment(payment, False)
        plan = self.planner.plan(payment, classification)
        with self.database.transaction() as connection:
            connection.execute("UPDATE recovery_actions SET approval_status='approved', execution_status='approved' WHERE case_id=? AND approval_status='pending'", (case_id,))
        self.ledger.append(case_id, "approval.granted", "human", {"strategy": plan.strategy, "reviewer": reviewer})
        return self._execute_allowed_action(case_id, payment, plan, "human_approved")

    def stop_case(self, case_id: str, reason: str = "operator_stopped") -> dict[str, Any]:
        self.get_case(case_id)
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE recovery_cases SET state = ?, closed_at = ? WHERE id = ?",
                (CaseState.STOPPED, utc_now(), case_id),
            )
            connection.execute(
                "UPDATE recovery_actions SET execution_status = 'cancelled' WHERE case_id = ? AND execution_status IN ('scheduled', 'pending_approval')",
                (case_id,),
            )
        self.ledger.append(case_id, "case.stopped", "human", {"reason": reason})
        return {"status": "stopped", "case_id": case_id}

    def _handle_captured(self, payment: PaymentFacts, target_case_id: str | None = None) -> dict[str, Any]:
        case = None
        if target_case_id:
            case = self.database.query_one("SELECT * FROM recovery_cases WHERE id = ?", (target_case_id,))
        if not case:
            case = self.database.query_one(
                "SELECT * FROM recovery_cases WHERE payment_id = ?", (payment.payment_id,)
            )
        if not case and payment.order_id:
            case = self.database.query_one(
                """
                SELECT rc.* FROM recovery_cases rc
                JOIN payments p ON p.payment_id = rc.payment_id
                WHERE p.order_id = ? ORDER BY rc.created_at DESC LIMIT 1
                """,
                (payment.order_id,),
            )
        if not case:
            # Check payment_links table by provider_link_id or reference_id
            link_match = self.database.query_one(
                """
                SELECT rc.* FROM recovery_cases rc
                JOIN payment_links pl ON pl.case_id = rc.id
                WHERE pl.provider_link_id = ? OR pl.reference_id = ?
                ORDER BY rc.created_at DESC LIMIT 1
                """,
                (payment.payment_id.replace("pay_", ""), f"recovery_{payment.payment_id}"),
            )
            if link_match:
                case = link_match
        if not case:
            return {"status": "captured_without_recovery_case", "payment_id": payment.payment_id}
        case_id = case["id"]
        if case["state"] == CaseState.RECOVERED:
            return {"status": "already_recovered", "case_id": case_id}
        intervention = self.database.query_one(
            """
            SELECT id FROM recovery_actions
            WHERE case_id = ? AND execution_status = 'executed'
            ORDER BY executed_at DESC LIMIT 1
            """,
            (case_id,),
        )
        attribution_type = "gross_recovery" if intervention else "organic_recovery"
        attribution_id = f"attr_{uuid.uuid4().hex[:14]}"
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE recovery_cases
                SET state = ?, closed_at = ?, next_action_at = NULL,
                    version = version + 1
                WHERE id = ?
                """,
                (CaseState.RECOVERED, utc_now(), case_id),
            )
            connection.execute(
                """
                UPDATE recovery_actions SET execution_status = 'cancelled'
                WHERE case_id = ? AND execution_status IN ('scheduled', 'pending_approval')
                """,
                (case_id,),
            )
            connection.execute(
                "UPDATE payment_links SET status = 'paid' WHERE case_id = ? AND status = 'created'",
                (case_id,),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO recovery_attributions
                (id, case_id, recovered_payment_id, intervention_id, amount_paise,
                 attribution_type, attributed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attribution_id,
                    case_id,
                    payment.payment_id,
                    intervention["id"] if intervention else None,
                    payment.amount_paise,
                    attribution_type,
                    utc_now(),
                ),
            )
        self.ledger.append(
            case_id,
            "payment.recovered",
            "razorpay",
            {
                "payment_id": payment.payment_id,
                "amount_paise": payment.amount_paise,
                "attribution_type": attribution_type,
            },
        )
        return {
            "status": "recovered",
            "case_id": case_id,
            "amount_paise": payment.amount_paise,
            "attribution_type": attribution_type,
        }

    @staticmethod
    def _payment_from_row(row: dict[str, Any] | None) -> PaymentFacts:
        if not row:
            raise KeyError("Payment not found")
        return PaymentFacts(
            payment_id=row["payment_id"],
            order_id=row["order_id"],
            amount_paise=row["amount_paise"],
            currency=row["currency"],
            status=row["status"],
            method=row["method"],
            provider=row["provider"],
            customer_name=row["customer_name"],
            email=row["email"],
            contact=row["contact"],
            error_code=row["error_code"],
            error_source=row["error_source"],
            error_step=row["error_step"],
            error_reason=row["error_reason"],
        )

    def get_case(self, case_id: str) -> dict[str, Any]:
        case = self.database.query_one("SELECT * FROM recovery_cases WHERE id = ?", (case_id,))
        if not case:
            raise KeyError(f"Recovery case {case_id} not found")
        return case

    def case_detail(self, case_id: str) -> dict[str, Any]:
        case = self.get_case(case_id)
        if case["state"] in {CaseState.OBSERVING, CaseState.WAITING, CaseState.ACTIONED}:
            try:
                self.reconcile_case(case_id)
                case = self.get_case(case_id)
            except Exception:
                pass
        payment = self.database.query_one(
            "SELECT * FROM payments WHERE payment_id = ?", (case["payment_id"],)
        )
        case = {
            **case,
            "customer_name": payment["customer_name"],
            "amount_paise": payment["amount_paise"],
            "currency": payment["currency"],
            "method": payment["method"],
            "provider": payment["provider"],
            "error_reason": payment["error_reason"],
        }
        actions = self.database.query_all(
            "SELECT * FROM recovery_actions WHERE case_id = ? ORDER BY created_at", (case_id,)
        )
        timeline = self.database.query_all(
            "SELECT * FROM audit_events WHERE case_id = ? ORDER BY sequence_number", (case_id,)
        )
        for event in timeline:
            event["canonical_payload"] = json.loads(event["canonical_payload"])
        communications = self.database.query_all(
            "SELECT * FROM recovery_communications WHERE case_id = ? ORDER BY created_at DESC", (case_id,)
        )
        promises = self.database.query_all(
            "SELECT * FROM promise_to_pay WHERE case_id = ? ORDER BY created_at DESC", (case_id,)
        )
        return {
            "case": case,
            "payment": payment,
            "actions": actions,
            "communications": communications,
            "promises": promises,
            "timeline": timeline,
            "ledger": self.ledger.verify(case_id),
            "workflow": workflow_trace(case, payment, timeline),
        }

    def list_cases(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.database.query_all(
            """
            SELECT rc.*, p.amount_paise, p.currency, p.customer_name, p.method,
                   p.provider, p.error_reason
            FROM recovery_cases rc JOIN payments p ON p.payment_id = rc.payment_id
            ORDER BY rc.created_at DESC LIMIT ?
            """,
            (limit,),
        )

    def create_promise_to_pay(self, case_id: str, promised_date: str, source_message: str, confidence: float = 0.95) -> dict[str, Any]:
        case = self.get_case(case_id)
        payment = self.database.query_one("SELECT * FROM payments WHERE payment_id = ?", (case["payment_id"],))
        promise_id = f"ptp_{uuid.uuid4().hex[:14]}"
        with self.database.transaction() as connection:
            connection.execute("""INSERT INTO promise_to_pay
                (id,case_id,promised_amount_paise,promised_date,status,source_message,confidence,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (promise_id,case_id,payment["amount_paise"],promised_date,"pending",source_message,confidence,utc_now()))
            connection.execute("UPDATE recovery_cases SET state=?, next_action_at=?, version=version+1 WHERE id=?",
                (CaseState.WAITING, promised_date, case_id))
        self.ledger.append(case_id,"promise_to_pay.created","customer",{"promise_id":promise_id,"promised_date":promised_date,"confidence":confidence,"source_message":source_message})
        try:
            from .tasks import schedule_promise_check
            task_id = schedule_promise_check(case_id, promised_date)
            self.ledger.append(case_id,"promise_to_pay.followup_scheduled","system",{"task_id":task_id,"promised_date":promised_date})
        except Exception as exc:
            self.ledger.append(case_id,"promise_to_pay.schedule_failed","system",{"error":type(exc).__name__})
        return self.database.query_one("SELECT * FROM promise_to_pay WHERE id=?",(promise_id,))

    def workflow_trace(self, case_id: str) -> dict[str, Any]:
        detail=self.case_detail(case_id)
        return workflow_trace(detail["case"], detail["payment"], detail["timeline"])

    def recent_activity(self, limit: int = 30) -> list[dict[str, Any]]:
        rows=self.database.query_all("""SELECT ae.*, p.customer_name, p.amount_paise FROM audit_events ae
            JOIN recovery_cases rc ON rc.id=ae.case_id JOIN payments p ON p.payment_id=rc.payment_id
            ORDER BY ae.created_at DESC LIMIT ?""",(limit,))
        for row in rows:
            row["canonical_payload"]=json.loads(row["canonical_payload"])
        return rows

    def list_approvals(self) -> list[dict[str, Any]]:
        return self.database.query_all("""
            SELECT ra.id AS action_id, ra.case_id, ra.action_type, ra.proposed_payload, ra.created_at,
                   p.customer_name, p.amount_paise, p.currency, rc.risk_score, rc.classification
            FROM recovery_actions ra
            JOIN recovery_cases rc ON rc.id=ra.case_id
            JOIN payments p ON p.payment_id=rc.payment_id
            WHERE ra.approval_status='pending' AND ra.execution_status='pending_approval'
            ORDER BY ra.created_at DESC
        """)

    def reject_case(self, case_id: str, reviewer: str, reason: str) -> dict[str, Any]:
        self.get_case(case_id)
        with self.database.transaction() as connection:
            connection.execute("UPDATE recovery_actions SET approval_status='rejected', execution_status='cancelled' WHERE case_id=? AND approval_status='pending'", (case_id,))
            connection.execute("UPDATE recovery_cases SET state=?, closed_at=? WHERE id=?", (CaseState.STOPPED, utc_now(), case_id))
        self.ledger.append(case_id, "approval.rejected", "human", {"reviewer": reviewer, "reason": reason})
        return {"status":"rejected","case_id":case_id}

    def global_ledger(self, limit: int = 250) -> list[dict[str, Any]]:
        rows=self.database.query_all("""SELECT ae.*, p.customer_name, p.amount_paise FROM audit_events ae
            JOIN recovery_cases rc ON rc.id=ae.case_id JOIN payments p ON p.payment_id=rc.payment_id
            ORDER BY ae.created_at DESC LIMIT ?""",(limit,))
        for row in rows: row["canonical_payload"]=json.loads(row["canonical_payload"])
        return rows

    def verify_global_ledger(self) -> dict[str, Any]:
        case_rows=self.database.query_all("SELECT id FROM recovery_cases")
        results=[self.ledger.verify(row["id"]) for row in case_rows]
        return {"valid": all(r["valid"] for r in results), "case_count": len(results), "event_count": sum(r["event_count"] for r in results), "violations": sum(0 if r["valid"] else 1 for r in results)}

    def communications(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.database.query_all("""SELECT c.*, p.customer_name, p.amount_paise FROM recovery_communications c
            JOIN recovery_cases rc ON rc.id=c.case_id JOIN payments p ON p.payment_id=rc.payment_id
            ORDER BY c.created_at DESC LIMIT ?""",(limit,))

    def dashboard_summary(self) -> dict[str, Any]:
        totals = self.database.query_one(
            """
            SELECT
              COALESCE(SUM(p.amount_paise), 0) AS at_risk_paise,
              COUNT(*) AS total_cases,
              SUM(CASE WHEN rc.state = 'recovered' THEN 1 ELSE 0 END) AS recovered_cases,
              SUM(CASE WHEN rc.state NOT IN ('recovered','stopped','exhausted') THEN 1 ELSE 0 END) AS active_cases
            FROM recovery_cases rc JOIN payments p ON p.payment_id = rc.payment_id
            """
        ) or {}
        recovered = self.database.query_one(
            """
            SELECT COALESCE(SUM(amount_paise), 0) AS recovered_paise,
                   COALESCE(SUM(CASE WHEN attribution_type = 'gross_recovery' THEN amount_paise ELSE 0 END), 0) AS assisted_paise
            FROM recovery_attributions
            """
        ) or {}
        messages = self.database.query_one(
            "SELECT COALESCE(SUM(message_count), 0) AS messages_sent FROM recovery_cases"
        ) or {}
        at_risk = int(totals.get("at_risk_paise") or 0)
        recovered_paise = int(recovered.get("recovered_paise") or 0)
        return {
            **totals,
            **recovered,
            **messages,
            "recovery_rate": round(recovered_paise / at_risk, 4) if at_risk else 0,
            "open_incidents": len([i for i in self.monitor.list_incidents() if i["state"] == "open"]),
        }
