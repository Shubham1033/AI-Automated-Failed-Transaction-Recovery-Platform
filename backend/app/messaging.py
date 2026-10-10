from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class MessageResult:
    provider_message_id: str
    status: str
    provider: str = "simulated"

class MessagingGateway:
    """Safe simulator used by benchmarks and local demos."""
    provider = "simulated"
    def send_email(self, to: str, subject: str, body: str) -> MessageResult:
        return MessageResult(
            provider_message_id=f"email_demo_{abs(hash((to, subject, body))) % 10**12}",
            status="simulated",
            provider=self.provider,
        )

class SESEmailGateway(MessagingGateway):
    provider = "aws_ses"
    def __init__(self, region: str, from_email: str):
        if not region or not from_email:
            raise ValueError("AWS_REGION and SES_FROM_EMAIL are required")
        import boto3
        self.client = boto3.client("sesv2", region_name=region)
        self.from_email = from_email

    def send_email(self, to: str, subject: str, body: str) -> MessageResult:
        import logging
        logger = logging.getLogger(__name__)
        try:
            response = self.client.send_email(
                FromEmailAddress=self.from_email,
                Destination={"ToAddresses": [to]},
                Content={"Simple": {"Subject": {"Data": subject}, "Body": {"Text": {"Data": body}}}},
            )
            return MessageResult(response["MessageId"], "accepted", self.provider)
        except Exception as exc:
            logger.warning("AWS SES send failed for recipient %s (likely unverified in SES sandbox): %s", to, exc)
            return MessageResult(f"ses_fallback_{abs(hash((to, subject, body))) % 10**12}", "ses_sandbox_unverified", self.provider)

class SMTPEmailGateway(MessagingGateway):
    provider = "smtp"
    def __init__(self, host: str, port: int, username: str, password: str, from_email: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email

    def send_email(self, to: str, subject: str, body: str) -> MessageResult:
        import smtplib
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_email or self.username
        msg["To"] = to
        msg.set_content(body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(msg)
            return MessageResult(f"smtp_{abs(hash((to, subject, body))) % 10**12}", "sent", self.provider)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("SMTP email send failed: %s", exc)
            return MessageResult(f"smtp_failed_{abs(hash((to, subject, body))) % 10**12}", "failed", self.provider)

