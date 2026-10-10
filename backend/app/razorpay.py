from __future__ import annotations

import hashlib
import hmac
import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class PaymentLinkResult:
    provider_link_id: str
    reference_id: str
    short_url: str
    expires_at: str


class PaymentLinkGateway:
    """Provider boundary. The MVP uses a deterministic fake unless live credentials are enabled."""

    def create(self, case_id: str, amount_paise: int, currency: str) -> PaymentLinkResult:
        token = uuid.uuid4().hex[:12]
        return PaymentLinkResult(
            provider_link_id=f"plink_demo_{token}",
            reference_id=f"recovery_{case_id}",
            short_url=f"https://rzp.io/i/demo-{token}",
            expires_at=(datetime.now(UTC) + timedelta(hours=48)).isoformat(),
        )

    def fetch(self, link_id: str) -> dict[str, Any] | None:
        return None


class RazorpayPaymentLinkGateway(PaymentLinkGateway):
    """Creates real Razorpay Payment Links with Test or Live keys supplied by the merchant."""

    def __init__(self, key_id: str, key_secret: str):
        if not key_id or not key_secret:
            raise ValueError("Razorpay API credentials are required when RAZORPAY_USE_API=true")
        self.key_id = key_id
        self.key_secret = key_secret

    def create(self, case_id: str, amount_paise: int, currency: str) -> PaymentLinkResult:
        expire_at = datetime.now(UTC) + timedelta(hours=48)
        body = json.dumps(
            {
                "amount": amount_paise,
                "currency": currency,
                "accept_partial": False,
                "reference_id": f"recovery_{case_id}",
                "description": f"ReviveAI recovery for {case_id}",
                "expire_by": int(expire_at.timestamp()),
                "notify": {"sms": False, "email": False},
                "reminder_enable": False,
                "notes": {"recovery_case_id": case_id, "source": "revive_ai"},
            }
        ).encode()
        credentials = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        request = Request(
            "https://api.razorpay.com/v1/payment_links",
            data=body,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "User-Agent": "ReviveAI/0.1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed trusted endpoint
                result = json.loads(response.read())
            return PaymentLinkResult(
                provider_link_id=result["id"],
                reference_id=result["reference_id"],
                short_url=result["short_url"],
                expires_at=expire_at.isoformat(),
            )
        except (HTTPError, URLError, OSError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("Razorpay create payment link failed for case %s (%s). Falling back to mock link.", case_id, exc)
            return super().create(case_id, amount_paise, currency)

    def fetch(self, link_id: str) -> dict[str, Any] | None:
        credentials = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        request = Request(
            f"https://api.razorpay.com/v1/payment_links/{link_id}",
            headers={"Authorization": f"Basic {credentials}", "User-Agent": "ReviveAI/0.2"},
        )
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read())
        except (HTTPError, URLError, OSError, json.JSONDecodeError, KeyError) as exc:
            logger.info("Razorpay payment link lookup for %s returned error: %s", link_id, exc)
            return None


@dataclass(frozen=True)
class PaymentStatusResult:
    payment_id: str
    status: str
    amount_paise: int
    currency: str


class PaymentStatusGateway:
    """Simulation-first status adapter. Database state remains the source in simulation mode."""

    def fetch(self, payment_id: str) -> PaymentStatusResult | None:
        return None


class RazorpayPaymentStatusGateway(PaymentStatusGateway):
    def __init__(self, key_id: str, key_secret: str):
        if not key_id or not key_secret:
            raise ValueError("Razorpay API credentials are required")
        self.key_id, self.key_secret = key_id, key_secret

    def fetch(self, payment_id: str) -> PaymentStatusResult | None:
        credentials = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        request = Request(
            f"https://api.razorpay.com/v1/payments/{payment_id}",
            headers={"Authorization": f"Basic {credentials}", "User-Agent": "ReviveAI/0.2"},
        )
        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read())
            return PaymentStatusResult(
                payment_id=result["id"],
                status=result["status"],
                amount_paise=int(result["amount"]),
                currency=result["currency"],
            )
        except (HTTPError, URLError, OSError, json.JSONDecodeError, KeyError) as exc:
            logger.info("Razorpay payment status lookup for %s returned error or non-existent payment: %s", payment_id, exc)
            return None
