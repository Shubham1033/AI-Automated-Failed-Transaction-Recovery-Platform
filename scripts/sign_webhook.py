#!/usr/bin/env python3
"""Print a Razorpay-compatible HMAC signature for a JSON payload file."""

from __future__ import annotations

import argparse
import hashlib
import hmac
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    parser.add_argument("--secret", required=True)
    args = parser.parse_args()
    body = args.payload.read_bytes()
    print(hmac.new(args.secret.encode(), body, hashlib.sha256).hexdigest())


if __name__ == "__main__":
    main()

