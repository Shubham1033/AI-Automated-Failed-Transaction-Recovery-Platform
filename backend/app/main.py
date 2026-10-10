from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import build_router
from .auth import ensure_bootstrap_admin
from .config import settings
from .factory import create_service

service=create_service(); ensure_bootstrap_admin(service.database)
app=FastAPI(title="ReviveAI API",description="Policy-bounded revenue recovery for Razorpay payments",version="0.2.0")
app.add_middleware(CORSMiddleware,allow_origins=list(settings.cors_origins),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(build_router(service,settings.razorpay_webhook_secret))
@app.get("/health")
async def health():
    return {"status":"ok","database":"ok" if service.database.ping() else "down"}
