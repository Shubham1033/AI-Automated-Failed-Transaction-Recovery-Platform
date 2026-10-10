from __future__ import annotations
from typing import Any, TypedDict
from .classifier import classify_payment
from .intelligence import synthetic_customer_context, assess_recovery
from .policy import PolicyContext, evaluate_policy

class GraphState(TypedDict, total=False):
    payment: Any; active_incident: bool; case: dict[str,Any]; classification: Any
    customer_context: Any; risk: Any; plan: Any; decision: Any; trace: list[dict[str,Any]]

def _mark(state:GraphState,node:str,detail:str)->list[dict[str,Any]]:
    return [*state.get("trace",[]),{"node":node,"status":"completed","detail":detail}]

class RecoveryGraph:
    """Real LangGraph orchestration when langgraph is installed; deterministic fallback only keeps unit tests portable."""
    def __init__(self, planner):
        self.planner=planner; self.graph=None
        try:
            from langgraph.graph import StateGraph, START, END
            g=StateGraph(GraphState)
            g.add_node("classify_failure",self._classify); g.add_node("load_customer_context",self._context)
            g.add_node("assess_recovery",self._score); g.add_node("plan_recovery",self._plan); g.add_node("policy_guard",self._policy)
            g.add_edge(START,"classify_failure"); g.add_edge("classify_failure","load_customer_context")
            g.add_edge("load_customer_context","assess_recovery"); g.add_edge("assess_recovery","plan_recovery")
            g.add_edge("plan_recovery","policy_guard"); g.add_edge("policy_guard",END)
            self.graph=g.compile()
        except ImportError: self.graph=None
    def _classify(self,s):
        c=classify_payment(s["payment"],active_incident=s["active_incident"]); return {"classification":c,"trace":_mark(s,"classify_failure",str(c.category))}
    def _context(self,s):
        c=synthetic_customer_context(s["payment"]); return {"customer_context":c,"trace":_mark(s,"load_customer_context","history loaded")}
    def _score(self,s):
        r=assess_recovery(s["payment"],s["classification"].category,s["customer_context"]); return {"risk":r,"trace":_mark(s,"assess_recovery",f"probability={r.recovery_probability:.2f}")}
    def _plan(self,s):
        p=self.planner.plan(s["payment"],s["classification"]); return {"plan":p,"trace":_mark(s,"plan_recovery",p.strategy)}
    def _policy(self,s):
        c=s["case"]; ctx=PolicyContext(payment_captured=s["payment"].status=="captured",active_incident=s["active_incident"],message_count=int(c["message_count"]),status_check_count=int(c["status_check_count"]),active_payment_link=bool(c["active_payment_link_id"]))
        d=evaluate_policy(s["payment"],s["plan"],ctx); return {"decision":d,"trace":_mark(s,"policy_guard",str(d.result))}
    def invoke(self,payment,active_incident,case):
        initial={"payment":payment,"active_incident":active_incident,"case":case,"trace":[]}
        if self.graph: return self.graph.invoke(initial)
        state=initial
        for fn in (self._classify,self._context,self._score,self._plan,self._policy): state={**state,**fn(state)}
        return state
