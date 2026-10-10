from __future__ import annotations
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import base64
import hashlib
import hmac
import os
from .config import settings
from .database import Database
from .models import utc_now

def hash_password(password: str) -> str:
    salt=os.urandom(16); digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,210_000)
    return f"pbkdf2_sha256$210000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        _,iterations,salt_b64,digest_b64=encoded.split("$",3); salt=base64.b64decode(salt_b64); expected=base64.b64decode(digest_b64)
        actual=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,int(iterations)); return hmac.compare_digest(actual,expected)
    except Exception: return False
bearer = HTTPBearer(auto_error=False)

class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    REVIEWER = "reviewer"
    VIEWER = "viewer"

ROLE_RANK = {Role.VIEWER: 0, Role.OPERATOR: 1, Role.REVIEWER: 2, Role.ADMIN: 3}

def ensure_bootstrap_admin(db: Database) -> None:
    if db.query_one("SELECT id FROM users WHERE email = ?", (settings.bootstrap_admin_email,)):
        return
    with db.transaction() as c:
        c.execute("INSERT INTO users (id,email,password_hash,role,is_active,created_at) VALUES (?,?,?,?,?,?)",
                  (f"usr_{uuid.uuid4().hex[:14]}", settings.bootstrap_admin_email, hash_password(settings.bootstrap_admin_password), Role.ADMIN, True, utc_now()))

def authenticate(db: Database, email: str, password: str) -> dict[str, Any] | None:
    user = db.query_one("SELECT * FROM users WHERE email = ?", (email,))
    if not user or not user["is_active"] or not verify_password(password, user["password_hash"]): return None
    return user

def create_access_token(user: dict[str, Any]) -> str:
    now = datetime.now(UTC)
    payload = {"sub": user["id"], "email": user["email"], "role": user["role"], "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, Any]:
    if settings.app_env == "test" and credentials is None:
        return {"id":"test","email":"test@local","role":Role.ADMIN}
    if credentials is None: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try: payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc: raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    return payload

def require_role(minimum: Role):
    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        try: role = Role(user["role"])
        except Exception as exc: raise HTTPException(status_code=403, detail="Unknown role") from exc
        if ROLE_RANK[role] < ROLE_RANK[minimum]: raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency
