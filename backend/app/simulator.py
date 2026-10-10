from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from typing import Any

from .service import RecoveryService


SCENARIOS = [
    ("provider_degradation", 0.20, "GATEWAY_ERROR", "provider_down", "HDFC"),
    ("late_authorization", 0.10, "SERVER_ERROR", "timeout", "ICICI"),
    ("insufficient_funds", 0.20, "BAD_REQUEST_ERROR", "insufficient_funds", "SBI"),
    ("authentication_failure", 0.15, "BAD_REQUEST_ERROR", "authentication_failed", "UPI"),
    ("expired_instrument", 0.15, "BAD_REQUEST_ERROR", "expired_card", "HDFC"),
    ("customer_actionable", 0.20, "BAD_REQUEST_ERROR", "payment_failed", "AXIS"),
]


@dataclass(frozen=True)
class SyntheticCase:
    index: int
    scenario: str
    amount_paise: int
    error_code: str
    error_reason: str
    provider: str
    organic_probability: float
    naive_probability: float
    smart_probability: float


def generate_cases(count: int = 100, seed: int = 42) -> list[SyntheticCase]:
    rng = random.Random(seed)
    cases: list[SyntheticCase] = []
    cumulative: list[tuple[float, tuple[str, float, str, str, str]]] = []
    total = 0.0
    for scenario in SCENARIOS:
        total += scenario[1]
        cumulative.append((total, scenario))
    probabilities = {
        "provider_degradation": (0.28, 0.29, 0.46),
        "late_authorization": (0.82, 0.82, 0.82),
        "insufficient_funds": (0.10, 0.18, 0.34),
        "authentication_failure": (0.08, 0.24, 0.43),
        "expired_instrument": (0.03, 0.12, 0.31),
        "customer_actionable": (0.12, 0.25, 0.44),
    }
    for index in range(count):
        draw = rng.random()
        selected = cumulative[-1][1]
        for threshold, scenario in cumulative:
            if draw <= threshold:
                selected = scenario
                break
        name, _, code, reason, provider = selected
        amount = rng.choice([49900, 99900, 149900, 249900, 499900, 999900])
        organic, naive, smart = probabilities[name]
        cases.append(
            SyntheticCase(
                index,
                name,
                amount,
                code,
                reason,
                provider,
                organic,
                naive,
                smart,
            )
        )
    return cases


def run_benchmark(count: int = 100, seed: int = 42) -> dict[str, Any]:
    """Paired seeded experiment: each arm sees the same customer propensity draw."""
    cases = generate_cases(count, seed)
    outcomes: dict[str, dict[str, int]] = {
        "organic": {"recovered_paise": 0, "recovered_cases": 0, "messages": 0, "cost_paise": 0},
        "naive": {"recovered_paise": 0, "recovered_cases": 0, "messages": 0, "cost_paise": 0},
        "revive_ai": {"recovered_paise": 0, "recovered_cases": 0, "messages": 0, "cost_paise": 0},
    }
    scenario_breakdown: dict[str, dict[str, int]] = {}
    for case in cases:
        propensity = random.Random(f"{seed}:{case.index}:paired").random()
        scenario_breakdown.setdefault(case.scenario, {"cases":0,"at_risk_paise":0,"revive_recovered_paise":0})
        scenario_breakdown[case.scenario]["cases"] += 1
        scenario_breakdown[case.scenario]["at_risk_paise"] += case.amount_paise
        for arm, probability in (("organic",case.organic_probability),("naive",case.naive_probability),("revive_ai",case.smart_probability)):
            if propensity < probability:
                outcomes[arm]["recovered_paise"] += case.amount_paise
                outcomes[arm]["recovered_cases"] += 1
                if arm == "revive_ai": scenario_breakdown[case.scenario]["revive_recovered_paise"] += case.amount_paise
        outcomes["naive"]["messages"] += 1
        outcomes["naive"]["cost_paise"] += 90
        if case.scenario not in {"provider_degradation", "late_authorization"}:
            outcomes["revive_ai"]["messages"] += 1
            outcomes["revive_ai"]["cost_paise"] += 90
        outcomes["revive_ai"]["cost_paise"] += 15  # orchestration/model allowance per case

    total_at_risk = sum(case.amount_paise for case in cases)
    for arm in outcomes.values():
        arm["recovery_rate_bps"] = round(arm["recovered_paise"] / total_at_risk * 10_000) if total_at_risk else 0
        arm["cost_per_recovered_1000_paise"] = round(arm["cost_paise"] / max(1, arm["recovered_paise"] / 100_000))
    incremental = outcomes["revive_ai"]["recovered_paise"] - outcomes["naive"]["recovered_paise"]
    naive = outcomes["naive"]["recovered_paise"]
    return {
        "seed":seed,"case_count":count,"total_at_risk_paise":total_at_risk,"arms":outcomes,
        "incremental_vs_naive_paise":incremental,
        "uplift_vs_naive_pct":round((incremental / naive * 100),1) if naive else 0,
        "messages_avoided":outcomes["naive"]["messages"]-outcomes["revive_ai"]["messages"],
        "scenario_breakdown":scenario_breakdown,
        "methodology":"Paired deterministic propensity simulation; identical synthetic customers are evaluated under each strategy.",
        "disclaimer":"Synthetic benchmark; probabilities and communication costs are explicit demo assumptions, not merchant results.",
    }


def make_failed_event(case: SyntheticCase, namespace: str = "demo") -> dict[str, Any]:
    payment_id = f"pay_{namespace}_{case.index:04d}"
    return {
        "id": f"evt_{namespace}_{case.index:04d}_failed",
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "order_id": f"order_{namespace}_{case.index:04d}",
                    "amount": case.amount_paise,
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi" if case.provider == "UPI" else "card",
                    "bank": case.provider,
                    "email": f"customer{case.index}@example.com",
                    "contact": f"+9190000{case.index:05d}",
                    "error_code": case.error_code,
                    "error_source": "bank",
                    "error_step": "payment_authorization",
                    "error_reason": case.error_reason,
                    "notes": {"customer_name": f"Customer {case.index + 1}"},
                }
            }
        },
    }


def seed_demo(service: RecoveryService, count: int = 30, seed: int = 42) -> dict[str, Any]:
    namespace = uuid.uuid4().hex[:6]
    results = []
    cases = generate_cases(count, seed)
    for case in cases:
        event = make_failed_event(case, namespace)
        results.append(service.ingest_event(event))
        if case.scenario == "late_authorization":
            captured = json_clone(event)
            captured["id"] = captured["id"].replace("failed", "captured")
            captured["event"] = "payment.captured"
            captured["payload"]["payment"]["entity"]["status"] = "captured"
            results.append(service.ingest_event(captured))
    return {
        "namespace": namespace,
        "created": len([result for result in results if result.get("status") != "duplicate"]),
        "summary": service.dashboard_summary(),
    }


def json_clone(value: Any) -> Any:
    import json

    return json.loads(json.dumps(value))

