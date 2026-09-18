import base64
import hashlib
import hmac
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import webhook
from webhook import _verify_signature, _within_clock_skew, grant_reward, issue_tracked_link

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


def test_issue_tracked_link_appends_partner_ref_id_to_origin_url(monkeypatch):
    monkeypatch.setenv("SHARELINK_PUBLISHER_ID", "pub-1")
    monkeypatch.setattr(webhook, "get_access_token", lambda: "tok")
    monkeypatch.setattr(
        webhook,
        "issue_link_with_origin",
        lambda token, taca_item_id, publisher_id: {"originUrl": "https://toss.im/item?x=1"},
    )
    url = issue_tracked_link(123, "anon hash/with special")
    assert url == "https://toss.im/item?x=1&partner_ref_id=anon%20hash%2Fwith%20special"


def test_issue_tracked_link_uses_question_mark_when_origin_has_no_query(monkeypatch):
    monkeypatch.setenv("SHARELINK_PUBLISHER_ID", "pub-1")
    monkeypatch.setattr(webhook, "get_access_token", lambda: "tok")
    monkeypatch.setattr(
        webhook,
        "issue_link_with_origin",
        lambda token, taca_item_id, publisher_id: {"originUrl": "https://toss.im/item"},
    )
    url = issue_tracked_link(123, "abc")
    assert url == "https://toss.im/item?partner_ref_id=abc"
