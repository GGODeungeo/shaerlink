"""Sharelink '주문 이벤트 수신' webhook receiver.

Verifies the HMAC-SHA256 signature per sharelink-docs.toss.im, then logs the
event. Reward-granting (the mTLS server-to-server promotion API call) isn't
wired in yet - added once the mTLS client certificate is issued.
"""
import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler

MAX_CLOCK_SKEW = timedelta(minutes=5)


def _verify_signature(raw_body: bytes, transmission_time: str, signature: str, secret: str) -> bool:
    if not (transmission_time and signature and signature.startswith("v1:")):
        return False
    message = raw_body + b":" + transmission_time.encode()
    expected = "v1:" + base64.b64encode(
        hmac.new(secret.encode(), message, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)


def _within_clock_skew(transmission_time: str) -> bool:
    try:
        sent_at = datetime.fromisoformat(transmission_time)
    except ValueError:
        return False
    now = datetime.now(timezone.utc)
    return abs(now - sent_at.astimezone(timezone.utc)) <= MAX_CLOCK_SKEW


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)
        transmission_time = self.headers.get("sharelink-webhook-transmission-time", "")
        signature = self.headers.get("sharelink-webhook-signature", "")
        secret = os.environ.get("SHARELINK_SECRET_KEY", "")

        if not secret or not _verify_signature(raw_body, transmission_time, signature, secret):
            self._respond(401, {"error": "invalid signature"})
            return
        if not _within_clock_skew(transmission_time):
            self._respond(401, {"error": "stale timestamp"})
            return

        event = json.loads(raw_body)
        print(f"[order-event] {event.get('eventType')} partnerRefId={event.get('partnerRefId')} "
              f"orderId={event.get('orderId')} amount={event.get('commissionBaseAmount')}")

        # TODO: on eventType == "PURCHASE", call the promotion get-key +
        # execute-promotion APIs (mTLS) using partnerRefId as x-anon-key,
        # with idempotency keyed on orderId.

        self._respond(200, {"received": True})

    def _respond(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)
