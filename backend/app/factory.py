from __future__ import annotations
from .config import settings
from .database import Database
from .messaging import MessagingGateway, SESEmailGateway, SMTPEmailGateway
from .planner import FallbackRecoveryPlanner, GeminiRecoveryPlanner, RecoveryPlanner
from .razorpay import PaymentLinkGateway, PaymentStatusGateway, RazorpayPaymentLinkGateway, RazorpayPaymentStatusGateway
from .service import RecoveryService

def create_service() -> RecoveryService:
    db=Database(settings.database_url)
    payment_links=RazorpayPaymentLinkGateway(settings.razorpay_key_id,settings.razorpay_key_secret) if settings.razorpay_use_api else PaymentLinkGateway()
    status_gateway=RazorpayPaymentStatusGateway(settings.razorpay_key_id,settings.razorpay_key_secret) if settings.razorpay_use_api else PaymentStatusGateway()
    planner=FallbackRecoveryPlanner(GeminiRecoveryPlanner(settings.gemini_api_key,settings.gemini_model)) if settings.ai_provider=="gemini" and settings.gemini_api_key else RecoveryPlanner()
    if settings.messaging_provider == "ses":
        messaging = SESEmailGateway(settings.aws_region, settings.ses_from_email)
    elif settings.messaging_provider == "smtp" and settings.smtp_host:
        messaging = SMTPEmailGateway(settings.smtp_host, settings.smtp_port, settings.smtp_username, settings.smtp_password, settings.email_from)
    else:
        messaging = MessagingGateway()
    return RecoveryService(db,planner=planner,payment_links=payment_links,payment_status=status_gateway,messaging=messaging)
