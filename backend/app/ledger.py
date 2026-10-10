from __future__ import annotations

import hashlib
import uuid
from typing import Any

from .database import Database, json_dumps
from .models import utc_now


GENESIS_HASH = "0" * 64


class RecoveryLedger:
    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _digest(
        previous_hash: str,
        case_id: str,
        sequence_number: int,
        event_type: str,
        payload: str,
        created_at: str,
    ) -> str:
        material = "|".join(
            [previous_hash, case_id, str(sequence_number), event_type, payload, created_at]
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def append(self, case_id: str, event_type: str, actor_type: str, payload: Any) -> str:
        canonical_payload = json_dumps(payload)
        created_at = utc_now()
        with self.database.transaction() as connection:
            previous = connection.execute(
                """
                SELECT sequence_number, event_hash FROM audit_events
                WHERE case_id = ? ORDER BY sequence_number DESC LIMIT 1
                """,
                (case_id,),
            ).fetchone()
            sequence = int(previous["sequence_number"]) + 1 if previous else 1
            previous_hash = str(previous["event_hash"]) if previous else GENESIS_HASH
            event_hash = self._digest(
                previous_hash,
                case_id,
                sequence,
                event_type,
                canonical_payload,
                created_at,
            )
            event_id = f"audit_{uuid.uuid4().hex[:16]}"
            connection.execute(
                """
                INSERT INTO audit_events
                (id, case_id, sequence_number, event_type, actor_type,
                 canonical_payload, previous_hash, event_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    case_id,
                    sequence,
                    event_type,
                    actor_type,
                    canonical_payload,
                    previous_hash,
                    event_hash,
                    created_at,
                ),
            )
        return event_hash

    def verify(self, case_id: str) -> dict[str, Any]:
        events = self.database.query_all(
            "SELECT * FROM audit_events WHERE case_id = ? ORDER BY sequence_number", (case_id,)
        )
        previous_hash = GENESIS_HASH
        for expected_sequence, event in enumerate(events, 1):
            calculated = self._digest(
                previous_hash,
                case_id,
                expected_sequence,
                event["event_type"],
                event["canonical_payload"],
                event["created_at"],
            )
            if (
                event["sequence_number"] != expected_sequence
                or event["previous_hash"] != previous_hash
                or event["event_hash"] != calculated
            ):
                return {
                    "valid": False,
                    "event_count": len(events),
                    "failed_at_sequence": expected_sequence,
                }
            previous_hash = event["event_hash"]
        return {"valid": True, "event_count": len(events), "head_hash": previous_hash}

