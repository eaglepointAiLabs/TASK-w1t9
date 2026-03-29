from __future__ import annotations

import hashlib
import hmac
import json
from base64 import urlsafe_b64encode
from datetime import datetime

from cryptography.fernet import Fernet

from app.services.time_utils import parse_iso_datetime_as_utc_naive


class PaymentSecurity:
    @staticmethod
    def derive_fernet_key(secret: str) -> bytes:
        return urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())

    def __init__(self, encryption_key: bytes) -> None:
        self.fernet = Fernet(encryption_key)

    def encrypt_secret(self, secret: str) -> str:
        return self.fernet.encrypt(secret.encode("utf-8")).decode("utf-8")

    def decrypt_secret(self, encrypted_secret: str) -> str:
        return self.fernet.decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")

    @staticmethod
    def canonical_payload(payload: dict) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def sign_payload(self, payload: dict, secret: str) -> str:
        canonical = self.canonical_payload(payload)
        return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_signature(self, payload: dict, signature: str, secret: str) -> bool:
        expected = self.sign_payload(payload, secret)
        return hmac.compare_digest(expected, signature)

    def payload_hash(self, payload: dict) -> str:
        return hashlib.sha256(self.canonical_payload(payload).encode("utf-8")).hexdigest()

    @staticmethod
    def parse_event_time(value: str | None) -> datetime | None:
        return parse_iso_datetime_as_utc_naive(value)
