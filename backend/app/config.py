from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./revive_ai.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_eager: bool = os.getenv("CELERY_EAGER", "false").lower() == "true"
    demo_time_scale: float = float(os.getenv("DEMO_TIME_SCALE", "1.0"))
    razorpay_key_id: str = os.getenv("RAZORPAY_KEY_ID", "")
    razorpay_key_secret: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    razorpay_webhook_secret: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "dev_webhook_secret")
    razorpay_use_api: bool = os.getenv("RAZORPAY_USE_API", "false").lower() == "true"
    ai_provider: str = os.getenv("AI_PROVIDER", "deterministic")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
    bootstrap_admin_email: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@revive.local")
    bootstrap_admin_password: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "ChangeMe123!")
    messaging_provider: str = os.getenv("MESSAGING_PROVIDER", "simulated")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    email_from: str = os.getenv("EMAIL_FROM", "")
    aws_region: str = os.getenv("AWS_REGION", "ap-south-1")
    ses_from_email: str = os.getenv("SES_FROM_EMAIL", os.getenv("EMAIL_FROM", ""))
    cors_origins: tuple[str, ...] = tuple(v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if v.strip())

settings = Settings()
