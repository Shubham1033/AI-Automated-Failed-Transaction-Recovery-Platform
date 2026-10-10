from __future__ import annotations
from typing import Any

WORKFLOW=("classify_failure","load_customer_context","assess_recovery","plan_recovery","policy_guard","execute_or_wait","verify_payment","attribute_or_continue")

def workflow_trace(case:dict[str,Any],payment:dict[str,Any],ledger:list[dict[str,Any]])->dict[str,Any]:
    graph_nodes=[]
    for row in ledger:
        if row.get("event_type")=="graph.executed":
            payload=row.get("canonical_payload",{})
            graph_nodes=payload.get("nodes",[]) if isinstance(payload,dict) else []
    by_name={n.get("node"):n for n in graph_nodes}
    seen={row["event_type"] for row in ledger}
    steps=[]
    for step in WORKFLOW:
        if step in by_name: steps.append({"step":step,**by_name[step]}); continue
        if step=="execute_or_wait": status="completed" if "action.executed" in seen or case["state"]=="waiting" else "pending"
        elif step=="verify_payment": status="completed" if "payment.reconciled" in seen or "payment.recovered" in seen else "pending"
        elif step=="attribute_or_continue": status="completed" if case["state"]=="recovered" else "pending"
        else: status="pending"
        steps.append({"step":step,"status":status,"detail":""})
    return {"engine":"langgraph-stategraph","case_id":case["id"],"state":case["state"],"steps":steps}
