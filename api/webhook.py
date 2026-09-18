"""Sharelink '주문 이벤트 수신' webhook receiver.

On a verified PURCHASE event, grants the sharelink click's promotion reward
via the apps-in-toss mTLS server-to-server API, using partnerRefId (the
buyer's getAnonymousKey() hash) as the anon-key target.
"""
import base64
import hashlib
import hmac
import http.client
import json
import os
import ssl
import tempfile
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler

MAX_CLOCK_SKEW = timedelta(minutes=5)
PROMOTION_API_HOST = "apps-in-toss-api.toss.im"

# ponytail: in-memory only - resets on cold start / differs per instance, so a
# retried webhook hitting a fresh instance can still double-grant. Move to a
# shared store (Vercel KV/Upstash) if duplicate rewards actually show up.
_processed_order_ids = set()


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


def _write_temp_pem(env_var: str) -> str:
    content = base64.b64decode(os.environ[env_var])
    fd, path = tempfile.mkstemp(suffix=".pem")
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


_mtls_context = None


def _mtls_ssl_context() -> ssl.SSLContext:
    global _mtls_context
    if _mtls_context is None:
        cert_path = _write_temp_pem("MTLS_CERT_B64")
        key_path = _write_temp_pem("MTLS_PRIVATE_KEY_B64")
        context = ssl.create_default_context()
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        _mtls_context = context
    return _mtls_context


def _promotion_api_post(path: str, anon_key: str, body: dict) -> dict:
    conn = http.client.HTTPSConnection(PROMOTION_API_HOST, context=_mtls_ssl_context(), timeout=10)
    try:
        conn.request(
            "POST",
            path,
            body=json.dumps(body),
            headers={"Content-Type": "application/json", "x-anon-key": anon_key},
        )
        resp = conn.getresponse()
        return json.loads(resp.read())
    finally:
        conn.close()


def grant_reward(anon_key: str, amount: int) -> dict:
    promotion_code = os.environ["PROMOTION_CODE"]

    key_resp = _promotion_api_post(
        "/api-partner/v1/apps-in-toss/promotion/execute-promotion/get-key", anon_key, {}
    )
    if key_resp.get("resultType") != "SUCCESS":
        return key_resp
    reward_key = key_resp["success"]["key"]

    return _promotion_api_post(
        "/api-partner/v1/apps-in-toss/promotion/execute-promotion",
        anon_key,
        {"promotionCode": promotion_code, "key": reward_key, "amount": amount},
    )


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
        event_type = event.get("eventType")
        order_id = event.get("orderId")
        partner_ref_id = event.get("partnerRefId")
        print(f"[order-event] {event_type} partnerRefId={partner_ref_id} orderId={order_id}")

        if event_type == "PURCHASE" and partner_ref_id and order_id not in _processed_order_ids:
            amount = int(os.environ.get("REWARD_AMOUNT_WON", "500"))
            result = grant_reward(partner_ref_id, amount)
            print(f"[reward] orderId={order_id} result={result}")
            if result.get("resultType") == "SUCCESS":
                _processed_order_ids.add(order_id)

        self._respond(200, {"received": True})

    def _respond(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)
