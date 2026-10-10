from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from .database import Database
from .models import utc_now


class RailHealthMonitor:
    def __init__(self, database: Database, minimum_attempts: int = 10, threshold: float = 0.60):
        self.database = database
        self.minimum_attempts = minimum_attempts
        self.threshold = threshold

    def active_incident(self, provider: str | None) -> dict[str, Any] | None:
        if not provider:
            return None
        return self.database.query_one(
            """
            SELECT * FROM payment_incidents
            WHERE provider = ? AND state = 'open'
            ORDER BY window_end DESC LIMIT 1
            """,
            (provider,),
        )

    def evaluate(self, provider: str | None, method: str | None) -> dict[str, Any] | None:
        if not provider:
            return None
        window_start = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        rows = self.database.query_all(
            """
            SELECT status FROM payments
            WHERE provider = ? AND updated_at >= ?
            """,
            (provider, window_start),
        )
        attempts = len(rows)
        failures = sum(1 for row in rows if row["status"] == "failed")
        rate = failures / attempts if attempts else 0
        if attempts < self.minimum_attempts or rate < self.threshold:
            return None
        existing = self.active_incident(provider)
        if existing:
            return existing
        incident_id = f"inc_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO payment_incidents
                (id, provider, method, attempt_count, failure_count, failure_rate,
                 state, window_start, window_end)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (incident_id, provider, method, attempts, failures, rate, window_start, now),
            )
        return self.active_incident(provider)

    def list_incidents(self) -> list[dict[str, Any]]:
        return self.database.query_all(
            "SELECT * FROM payment_incidents ORDER BY window_end DESC LIMIT 50"
        )

