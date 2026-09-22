"""Sharelink '주문 이벤트 수신' webhook receiver.

On a verified PURCHASE event, grants the sharelink click's promotion reward
via the apps-in-toss mTLS server-to-server API, using partnerRefId (the
buyer's getAnonymousKey() hash) as the anon-key target.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import json
import os
import ssl
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler
from pathlib import Path

MAX_CLOCK_SKEW = timedelta(minutes=5)
PRODUCTS_JSON_PATH = Path(__file__).resolve().parent.parent / "app-data" / "products.json"
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


def is_reward_eligible(event: dict, min_purchase_amount: int, processed_order_ids: set) -> bool:
    return (
        event.get("eventType") == "PURCHASE"
        and bool(event.get("partnerRefId"))
        and event.get("orderId") not in processed_order_ids
        and (event.get("commissionBaseAmount") or 0) >= min_purchase_amount
    )


def grant_reward(anon_key: str, amount: int, promotion_code: str | None = None) -> dict:
    promotion_code = promotion_code or os.environ["PROMOTION_CODE"]

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


def grant_click_reward(anon_key: str) -> None:
    """Best-effort reward grant for clicking through to the sharelink itself,
    separate from the PURCHASE-triggered reward above (different promotion,
    tiny amount). Never raises - a failed/capped grant (daily limit hit,
    promotion paused) must not break link issuance."""
    click_promotion_code = os.environ.get("CLICK_PROMOTION_CODE")
    if not click_promotion_code:
        return
    amount = int(os.environ.get("CLICK_REWARD_AMOUNT_WON", "1"))
    try:
        result = grant_reward(anon_key, amount, promotion_code=click_promotion_code)
        print(f"[click-reward] anonKey={anon_key} result={result}")
    except Exception as e:
        print(f"[click-reward] failed for anonKey={anon_key}: {e}")


def issue_tracked_link(taca_item_id: int, anon_key: str) -> str:
    """Issues a fresh sharelink for this click and tags its originUrl with
    partner_ref_id=anon_key, so a later PURCHASE webhook can attribute the
    order back to this app user.

    Sharelink's Open API enforces a source-IP allowlist that Vercel's
    dynamic egress IP can't satisfy, so the actual issuance happens on a
    small static-IP relay droplet instead - this just forwards to it."""
    req = urllib.request.Request(
        os.environ["RELAY_URL"],
        data=json.dumps({"tacaItemId": taca_item_id}).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "x-relay-token": os.environ["RELAY_TOKEN"]},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        link = json.loads(resp.read())

    origin = link["originUrl"]
    sep = "&" if "?" in origin else "?"
    return f"{origin}{sep}partner_ref_id={urllib.parse.quote(anon_key, safe='')}"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/products"):
            self._handle_products_request()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path.startswith("/api/link"):
            self._handle_link_request()
        elif self.path.startswith("/api/test-reward"):
            self._handle_test_reward_request()
        else:
            self._handle_order_event()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, x-internal-token")
        self.end_headers()

    def _handle_products_request(self):
        try:
            payload = PRODUCTS_JSON_PATH.read_bytes()
        except FileNotFoundError:
            self._respond(404, {"error": "products.json not found"}, cors=True)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _handle_order_event(self):
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
        order_id = event.get("orderId")
        min_purchase = int(os.environ.get("MIN_PURCHASE_AMOUNT_WON", "5000"))
        print(f"[order-event] {event.get('eventType')} partnerRefId={event.get('partnerRefId')} "
              f"orderId={order_id} amount={event.get('commissionBaseAmount')}")

        if is_reward_eligible(event, min_purchase, _processed_order_ids):
            amount = int(os.environ.get("REWARD_AMOUNT_WON", "500"))
            result = grant_reward(event["partnerRefId"], amount)
            print(f"[reward] orderId={order_id} result={result}")
            if result.get("resultType") == "SUCCESS":
                _processed_order_ids.add(order_id)

        self._respond(200, {"received": True})

    def _handle_link_request(self):
        token = self.headers.get("x-internal-token", "")
        if not hmac.compare_digest(token, os.environ.get("LINK_API_TOKEN", "")):
            self._respond(401, {"error": "unauthorized"}, cors=True)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(content_length) or b"{}")
            taca_item_id = int(body["tacaItemId"])
            anon_key = str(body["anonKey"])
        except (json.JSONDecodeError, KeyError, ValueError):
            self._respond(400, {"error": "tacaItemId and anonKey are required"}, cors=True)
            return

        print(f"[link] request tacaItemId={taca_item_id} anonKey={anon_key}")
        try:
            url = issue_tracked_link(taca_item_id, anon_key)
        except Exception as e:
            print(f"[link] issue failed for tacaItemId={taca_item_id}: {e}")
            self._respond(502, {"error": "link issuance failed"}, cors=True)
            return

        grant_click_reward(anon_key)
        self._respond(200, {"url": url}, cors=True)

    def _handle_test_reward_request(self):
        """Manual test hook for the promotion pre-launch gate: lets us call
        execute-promotion with a TEST_-prefixed code (see promotion docs)
        without touching the live PROMOTION_CODE/CLICK_PROMOTION_CODE env
        vars. Same auth token as /api/link since both are internal-only."""
        token = self.headers.get("x-internal-token", "")
        if not hmac.compare_digest(token, os.environ.get("LINK_API_TOKEN", "")):
            self._respond(401, {"error": "unauthorized"}, cors=True)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(content_length) or b"{}")
            promotion_code = str(body["promotionCode"])
            anon_key = str(body["anonKey"])
            amount = int(body["amount"])
        except (json.JSONDecodeError, KeyError, ValueError):
            self._respond(400, {"error": "promotionCode, anonKey and amount are required"}, cors=True)
            return

        result = grant_reward(anon_key, amount, promotion_code=promotion_code)
        print(f"[test-reward] promotionCode={promotion_code} anonKey={anon_key} result={result}")
        self._respond(200, result, cors=True)

    def _respond(self, status: int, body: dict, cors: bool = False):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)
