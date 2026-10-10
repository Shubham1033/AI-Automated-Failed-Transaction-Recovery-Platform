from __future__ import annotations

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Float, ForeignKey, Index, Integer, MetaData,
    String, Table, Text, UniqueConstraint, text
)
from sqlalchemy.engine import Engine

metadata = MetaData()

webhook_events = Table("webhook_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_key", String(255), nullable=False, unique=True),
    Column("event_type", String(100), nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("raw_payload", Text, nullable=False),
    Column("signature_verified", Boolean, nullable=False),
    Column("created_at", String(64), nullable=False),
)
payments = Table("payments", metadata,
    Column("payment_id", String(255), primary_key=True), Column("order_id", String(255)),
    Column("amount_paise", Integer, nullable=False), Column("currency", String(8), nullable=False),
    Column("status", String(50), nullable=False), Column("method", String(50)), Column("provider", String(100)),
    Column("customer_name", String(255), nullable=False), Column("email", String(255)), Column("contact", String(50)),
    Column("error_code", String(100)), Column("error_source", String(100)), Column("error_step", String(100)), Column("error_reason", String(255)),
    Column("created_at", String(64), nullable=False), Column("updated_at", String(64), nullable=False),
    CheckConstraint("amount_paise >= 0", name="ck_payments_amount_nonnegative"),
)
recovery_cases = Table("recovery_cases", metadata,
    Column("id", String(64), primary_key=True), Column("payment_id", String(255), ForeignKey("payments.payment_id"), nullable=False, unique=True),
    Column("state", String(50), nullable=False), Column("classification", String(100), nullable=False), Column("risk_score", Float, nullable=False, server_default="0"),
    Column("current_strategy", String(100)), Column("message_count", Integer, nullable=False, server_default="0"), Column("status_check_count", Integer, nullable=False, server_default="0"),
    Column("active_payment_link_id", String(64)), Column("next_action_at", String(64)), Column("version", Integer, nullable=False, server_default="0"),
    Column("created_at", String(64), nullable=False), Column("closed_at", String(64)),
)
recovery_actions = Table("recovery_actions", metadata,
    Column("id", String(64), primary_key=True), Column("case_id", String(64), ForeignKey("recovery_cases.id"), nullable=False),
    Column("action_type", String(100), nullable=False), Column("idempotency_key", String(64), nullable=False, unique=True), Column("proposed_payload", Text, nullable=False),
    Column("policy_result", String(50), nullable=False), Column("approval_status", String(50), nullable=False, server_default="not_required"), Column("execution_status", String(50), nullable=False),
    Column("scheduled_at", String(64)), Column("executed_at", String(64)), Column("celery_task_id", String(255)), Column("created_at", String(64), nullable=False),
)
payment_links = Table("payment_links", metadata,
    Column("id", String(64), primary_key=True), Column("case_id", String(64), ForeignKey("recovery_cases.id"), nullable=False),
    Column("provider_link_id", String(255), nullable=False, unique=True), Column("reference_id", String(255), nullable=False, unique=True), Column("amount_paise", Integer, nullable=False),
    Column("currency", String(8), nullable=False), Column("status", String(50), nullable=False), Column("short_url", Text, nullable=False), Column("expires_at", String(64), nullable=False), Column("created_at", String(64), nullable=False),
)
Index("one_active_link_per_case", payment_links.c.case_id, unique=True, postgresql_where=text("status = 'created'"), sqlite_where=text("status = 'created'"))
recovery_attributions = Table("recovery_attributions", metadata,
    Column("id", String(64), primary_key=True), Column("case_id", String(64), ForeignKey("recovery_cases.id"), nullable=False), Column("recovered_payment_id", String(255), nullable=False, unique=True),
    Column("intervention_id", String(64)), Column("amount_paise", Integer, nullable=False), Column("attribution_type", String(50), nullable=False), Column("attributed_at", String(64), nullable=False),
)
payment_incidents = Table("payment_incidents", metadata,
    Column("id", String(64), primary_key=True), Column("provider", String(100), nullable=False), Column("method", String(50)), Column("attempt_count", Integer, nullable=False), Column("failure_count", Integer, nullable=False),
    Column("failure_rate", Float, nullable=False), Column("state", String(50), nullable=False), Column("window_start", String(64), nullable=False), Column("window_end", String(64), nullable=False), Column("resolved_at", String(64)),
)
audit_events = Table("audit_events", metadata,
    Column("id", String(64), primary_key=True), Column("case_id", String(64), ForeignKey("recovery_cases.id"), nullable=False), Column("sequence_number", Integer, nullable=False),
    Column("event_type", String(100), nullable=False), Column("actor_type", String(50), nullable=False), Column("canonical_payload", Text, nullable=False), Column("previous_hash", String(64), nullable=False), Column("event_hash", String(64), nullable=False), Column("created_at", String(64), nullable=False),
    UniqueConstraint("case_id", "sequence_number", name="uq_audit_case_sequence"),
)
users = Table("users", metadata,
    Column("id", String(64), primary_key=True), Column("email", String(255), nullable=False, unique=True), Column("password_hash", Text, nullable=False),
    Column("role", String(50), nullable=False), Column("is_active", Boolean, nullable=False, server_default=text("true")), Column("created_at", String(64), nullable=False),
)

promise_to_pay = Table("promise_to_pay", metadata,
    Column("id", String(64), primary_key=True), Column("case_id", String(64), ForeignKey("recovery_cases.id"), nullable=False),
    Column("promised_amount_paise", Integer, nullable=False), Column("promised_date", String(32), nullable=False),
    Column("status", String(50), nullable=False, server_default="pending"), Column("source_message", Text, nullable=False),
    Column("confidence", Float, nullable=False), Column("created_at", String(64), nullable=False), Column("resolved_at", String(64)),
)

recovery_communications = Table("recovery_communications", metadata,
    Column("id", String(64), primary_key=True),
    Column("case_id", String(64), ForeignKey("recovery_cases.id"), nullable=False),
    Column("channel", String(32), nullable=False, server_default="email"),
    Column("provider", String(50), nullable=False),
    Column("recipient", String(255), nullable=False),
    Column("subject", String(255), nullable=False),
    Column("body", Text, nullable=False),
    Column("language", String(32), nullable=False, server_default="hinglish"),
    Column("status", String(50), nullable=False),
    Column("provider_message_id", String(255)),
    Column("payment_link", Text),
    Column("created_at", String(64), nullable=False),
    Column("sent_at", String(64)),
)

def create_schema(engine: Engine) -> None:
    metadata.create_all(engine)
