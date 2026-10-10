from __future__ import annotations
import json
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from .auth import Role, authenticate, create_access_token, current_user, require_role
from .razorpay import verify_webhook_signature
from .service import RecoveryService
from .simulator import run_benchmark, seed_demo

class SimulationRequest(BaseModel):
    count:int=Field(default=1000,ge=10,le=5000); seed:int=42
class StopRequest(BaseModel): reason:str=Field(default="operator_stopped",max_length=200)
class LoginRequest(BaseModel): email:str; password:str
class PromiseRequest(BaseModel): promised_date:str=Field(min_length=8,max_length=32); source_message:str=Field(min_length=1,max_length=500); confidence:float=Field(default=.95,ge=0,le=1)
class RejectRequest(BaseModel): reason:str=Field(default="Reviewer rejected recovery action",min_length=3,max_length=300)

def build_router(service: RecoveryService, webhook_secret: str) -> APIRouter:
    router=APIRouter(prefix="/api/v1")
    @router.post("/auth/login")
    async def login(body: LoginRequest):
        user=authenticate(service.database,body.email,body.password)
        if not user: raise HTTPException(status_code=401,detail="Invalid credentials")
        return {"access_token":create_access_token(user),"token_type":"bearer","role":user["role"]}
    @router.get("/auth/me")
    async def me(user=Depends(current_user)): return user
    @router.post("/webhooks/razorpay")
    async def webhook(request:Request):
        raw=await request.body(); signature=request.headers.get("x-razorpay-signature","")
        if not verify_webhook_signature(raw,signature,webhook_secret): raise HTTPException(status_code=401,detail="Invalid webhook signature")
        try: payload=json.loads(raw)
        except json.JSONDecodeError as exc: raise HTTPException(status_code=400,detail="Invalid JSON payload") from exc
        return service.ingest_event(payload,raw_body=raw,signature_verified=True)
    @router.post("/demo/events")
    async def demo_event(payload:dict[str,Any], user=Depends(require_role(Role.OPERATOR))): return service.ingest_event(payload,signature_verified=True)
    @router.post("/demo/seed")
    async def demo_seed(body:SimulationRequest,user=Depends(require_role(Role.OPERATOR))): return seed_demo(service,body.count,body.seed)
    @router.post("/simulations/run")
    async def simulate(body:SimulationRequest,user=Depends(require_role(Role.OPERATOR))): return run_benchmark(body.count,body.seed)
    @router.get("/dashboard/summary")
    async def summary(user=Depends(current_user)): return service.dashboard_summary()
    @router.get("/dashboard/activity")
    async def activity(limit:int=30,user=Depends(current_user)): return service.recent_activity(min(max(limit,1),100))
    @router.post("/demo/judge")
    async def judge_demo(user=Depends(require_role(Role.OPERATOR))):
        seeded=seed_demo(service,30,2026); benchmark=run_benchmark(1000,2026)
        return {"seeded":seeded,"benchmark":benchmark,"demo_mode":"synthetic_reproducible"}
    @router.get("/cases")
    async def cases(limit:int=100,user=Depends(current_user)): return service.list_cases(min(max(limit,1),500))
    @router.get("/cases/{case_id}")
    async def detail(case_id:str,user=Depends(current_user)):
        try:return service.case_detail(case_id)
        except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    @router.post("/cases/{case_id}/approve")
    async def approve(case_id:str,user=Depends(require_role(Role.REVIEWER))):
        try:return service.approve_case(case_id,user.get("email","reviewer"))
        except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    @router.post("/cases/{case_id}/reject")
    async def reject(case_id:str,body:RejectRequest,user=Depends(require_role(Role.REVIEWER))):
        try:return service.reject_case(case_id,user.get("email","reviewer"),body.reason)
        except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    @router.get("/approvals")
    async def approvals(user=Depends(require_role(Role.REVIEWER))): return service.list_approvals()
    @router.get("/communications")
    async def communications(limit:int=100,user=Depends(current_user)): return service.communications(min(max(limit,1),500))
    @router.get("/ledger")
    async def ledger(limit:int=250,user=Depends(current_user)): return service.global_ledger(min(max(limit,1),1000))
    @router.get("/ledger/verify")
    async def ledger_verify(user=Depends(current_user)): return service.verify_global_ledger()
    @router.post("/cases/{case_id}/reconcile")
    async def reconcile(case_id:str,user=Depends(require_role(Role.OPERATOR))):
        try:return service.reconcile_case(case_id)
        except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    @router.post("/cases/{case_id}/stop")
    async def stop(case_id:str,body:StopRequest,user=Depends(require_role(Role.OPERATOR))):
        try:return service.stop_case(case_id,body.reason)
        except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    @router.get("/cases/{case_id}/ledger/verify")
    async def verify(case_id:str,user=Depends(current_user)):
        try:service.get_case(case_id)
        except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
        return service.ledger.verify(case_id)
    @router.post("/cases/{case_id}/promise-to-pay")
    async def promise(case_id:str,body:PromiseRequest,user=Depends(require_role(Role.OPERATOR))):
        try:return service.create_promise_to_pay(case_id,body.promised_date,body.source_message,body.confidence)
        except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    @router.get("/cases/{case_id}/workflow-trace")
    async def trace(case_id:str,user=Depends(current_user)):
        try:return service.workflow_trace(case_id)
        except KeyError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    @router.get("/incidents")
    async def incidents(user=Depends(current_user)): return service.monitor.list_incidents()
    return router
