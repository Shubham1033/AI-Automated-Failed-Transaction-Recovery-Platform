import hashlib
import hmac
import unittest

from app.razorpay import verify_webhook_signature


class SignatureTests(unittest.TestCase):
    def test_valid_signature(self) -> None:
        body = b'{"event":"payment.failed"}'
        secret = "test_secret"
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook_signature(body, signature, secret))

    def test_invalid_signature(self) -> None:
        self.assertFalse(verify_webhook_signature(b"body", "bad", "secret"))


if __name__ == "__main__":
    unittest.main()

