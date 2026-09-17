import base64
import hashlib
import hmac
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from webhook import _verify_signature, _within_clock_skew

SECRET = "test-secret"


def _sign(body: bytes, transmission_time: str) -> str:
    message = body + b":" + transmission_time.encode()
    return "v1:" + base64.b64encode(hmac.new(SECRET.encode(), message, hashlib.sha256).digest()).decode()


def test_verify_signature_accepts_correctly_signed_body():
    body = b'{"eventType":"PURCHASE"}'
    ts = datetime.now(timezone.utc).isoformat()
    assert _verify_signature(body, ts, _sign(body, ts), SECRET)


def test_verify_signature_rejects_tampered_body():
    ts = datetime.now(timezone.utc).isoformat()
    signature = _sign(b'{"eventType":"PURCHASE"}', ts)
    assert not _verify_signature(b'{"eventType":"CANCEL"}', ts, signature, SECRET)


def test_verify_signature_rejects_wrong_secret():
    body = b'{"eventType":"PURCHASE"}'
    ts = datetime.now(timezone.utc).isoformat()
    signature = _sign(body, ts)
    assert not _verify_signature(body, ts, signature, "wrong-secret")


def test_within_clock_skew_accepts_recent_timestamp():
    assert _within_clock_skew(datetime.now(timezone.utc).isoformat())


def test_within_clock_skew_rejects_old_timestamp():
    old = datetime.now(timezone.utc) - timedelta(minutes=10)
    assert not _within_clock_skew(old.isoformat())
