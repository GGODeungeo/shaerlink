import base64
import hashlib
import hmac
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import webhook
from webhook import (
    _verify_signature,
    _within_clock_skew,
    grant_click_reward,
    grant_reward,
    is_reward_eligible,
    issue_tracked_link,
)

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


def test_grant_reward_passes_key_from_get_key_into_execute_promotion(monkeypatch):
    monkeypatch.setenv("PROMOTION_CODE", "PROMO123")
    calls = []

    def fake_post(path, anon_key, body):
        calls.append((path, anon_key, body))
        if path.endswith("/get-key"):
            return {"resultType": "SUCCESS", "success": {"key": "the-key"}}
        return {"resultType": "SUCCESS", "success": {"key": "the-key"}}

    monkeypatch.setattr(webhook, "_promotion_api_post", fake_post)
    result = grant_reward("anon-hash", 500)

    assert result["resultType"] == "SUCCESS"
    assert calls[0][0].endswith("/get-key")
    assert calls[1][1] == "anon-hash"
    assert calls[1][2] == {"promotionCode": "PROMO123", "key": "the-key", "amount": 500}


def test_grant_reward_stops_and_returns_error_if_get_key_fails(monkeypatch):
    monkeypatch.setenv("PROMOTION_CODE", "PROMO123")
    calls = []
    monkeypatch.setattr(
        webhook,
        "_promotion_api_post",
        lambda path, anon_key, body: calls.append(path) or {"resultType": "FAIL", "error": {"errorCode": "4100"}},
    )
    result = grant_reward("anon-hash", 500)

    assert result["resultType"] == "FAIL"
    assert len(calls) == 1


def test_grant_reward_uses_explicit_promotion_code_over_env(monkeypatch):
    monkeypatch.setenv("PROMOTION_CODE", "PURCHASE_PROMO")
    calls = []

    def fake_post(path, anon_key, body):
        calls.append((path, anon_key, body))
        return {"resultType": "SUCCESS", "success": {"key": "the-key"}}

    monkeypatch.setattr(webhook, "_promotion_api_post", fake_post)
    grant_reward("anon-hash", 1, promotion_code="CLICK_PROMO")

    assert calls[1][2]["promotionCode"] == "CLICK_PROMO"


def test_grant_click_reward_noop_when_no_click_promotion_configured(monkeypatch):
    monkeypatch.delenv("CLICK_PROMOTION_CODE", raising=False)
    calls = []
    monkeypatch.setattr(webhook, "grant_reward", lambda *a, **k: calls.append((a, k)))

    grant_click_reward("anon-hash")

    assert calls == []


def test_grant_click_reward_calls_grant_reward_with_click_promotion_and_amount(monkeypatch):
    monkeypatch.setenv("CLICK_PROMOTION_CODE", "CLICK_PROMO")
    monkeypatch.setenv("CLICK_REWARD_AMOUNT_WON", "1")
    calls = []
    monkeypatch.setattr(
        webhook, "grant_reward", lambda anon_key, amount, promotion_code=None: calls.append((anon_key, amount, promotion_code)) or {"resultType": "SUCCESS"}
    )

    grant_click_reward("anon-hash")

    assert calls == [("anon-hash", 1, "CLICK_PROMO")]


def test_grant_click_reward_swallows_errors(monkeypatch):
    monkeypatch.setenv("CLICK_PROMOTION_CODE", "CLICK_PROMO")

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(webhook, "grant_reward", boom)

    grant_click_reward("anon-hash")  # must not raise


class _FakeUrlopenResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self._body


def test_issue_tracked_link_appends_partner_ref_id_to_origin_url(monkeypatch):
    monkeypatch.setenv("RELAY_URL", "http://relay:8080/")
    monkeypatch.setenv("RELAY_TOKEN", "relay-secret")
    monkeypatch.setattr(
        webhook.urllib.request,
        "urlopen",
        lambda req, timeout: _FakeUrlopenResponse(json.dumps({"originUrl": "https://toss.im/item?x=1"}).encode()),
    )
    url = issue_tracked_link(123, "anon hash/with special")
    assert url == "https://toss.im/item?x=1&partner_ref_id=anon%20hash%2Fwith%20special"


def test_issue_tracked_link_uses_question_mark_when_origin_has_no_query(monkeypatch):
    monkeypatch.setenv("RELAY_URL", "http://relay:8080/")
    monkeypatch.setenv("RELAY_TOKEN", "relay-secret")
    monkeypatch.setattr(
        webhook.urllib.request,
        "urlopen",
        lambda req, timeout: _FakeUrlopenResponse(json.dumps({"originUrl": "https://toss.im/item"}).encode()),
    )
    url = issue_tracked_link(123, "abc")
    assert url == "https://toss.im/item?partner_ref_id=abc"


def _purchase_event(**overrides):
    event = {
        "eventType": "PURCHASE",
        "partnerRefId": "anon-hash",
        "orderId": "order-1",
        "commissionBaseAmount": 5000,
    }
    event.update(overrides)
    return event


def test_is_reward_eligible_accepts_purchase_at_or_above_minimum():
    assert is_reward_eligible(_purchase_event(commissionBaseAmount=5000), 5000, set())
    assert is_reward_eligible(_purchase_event(commissionBaseAmount=9999), 5000, set())


def test_is_reward_eligible_rejects_purchase_below_minimum():
    assert not is_reward_eligible(_purchase_event(commissionBaseAmount=4999), 5000, set())


def test_is_reward_eligible_rejects_cancel_events():
    assert not is_reward_eligible(_purchase_event(eventType="CANCEL"), 5000, set())


def test_is_reward_eligible_rejects_already_processed_order():
    assert not is_reward_eligible(_purchase_event(orderId="order-1"), 5000, {"order-1"})


def test_is_reward_eligible_rejects_missing_partner_ref_id():
    assert not is_reward_eligible(_purchase_event(partnerRefId=None), 5000, set())
