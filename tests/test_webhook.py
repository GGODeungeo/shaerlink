import base64
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import webhook
from webhook import (
    _verify_signature,
    _within_clock_skew,
    build_products_query,
    decode_cursor,
    encode_cursor,
    fetch_home_products,
    fetch_products_page,
    grant_click_reward,
    grant_reward,
    is_reward_eligible,
    issue_tracked_link,
)
from sharelink_api import _load_dotenv

_load_dotenv()  # module level - skipif가 실제 env를 봐야 한다 (지연 로딩 전에 읽으면 오탐)

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


def test_encode_decode_cursor_roundtrip():
    row = {"sort_value": 42, "source": "sharelink", "source_item_id": "abc"}
    cursor = encode_cursor(row)
    assert decode_cursor(cursor) == (42, "sharelink", "abc")


def test_build_products_query_by_category_first_page():
    sql, params = build_products_query(
        category="식품", search=None, sort="recommend", cursor=None, limit=20
    )
    assert "category = %s" in sql
    assert "order by review_count desc" in sql
    assert params == ["식품", 20]


def test_build_products_query_by_category_with_cursor():
    cursor = encode_cursor({"sort_value": 100, "source": "sharelink", "source_item_id": "x"})
    sql, params = build_products_query(
        category="식품", search=None, sort="recommend", cursor=cursor, limit=20
    )
    assert "review_count, source, source_item_id) < (%s, %s, %s)" in sql
    assert params == ["식품", 100, "sharelink", "x", 20]


def test_build_products_query_by_search_uses_ilike():
    sql, params = build_products_query(
        category=None, search="세탁", sort="price", cursor=None, limit=20
    )
    assert "name ilike %s" in sql
    assert "order by price asc" in sql
    assert params == ["%세탁%", 20]


def test_build_products_query_price_sort_cursor_uses_greater_than():
    cursor = encode_cursor({"sort_value": 5000, "source": "sharelink", "source_item_id": "y"})
    sql, params = build_products_query(
        category=None, search="세탁", sort="price", cursor=cursor, limit=20
    )
    assert "price, source, source_item_id) > (%s, %s, %s)" in sql
    assert params == ["%세탁%", 5000, "sharelink", "y", 20]


def test_build_products_query_rejects_unknown_sort():
    import pytest

    with pytest.raises(ValueError):
        build_products_query(category="식품", search=None, sort="bogus", cursor=None, limit=20)


class _FakeCursor:
    def __init__(self, rows, columns):
        self._rows = rows
        self.description = [(c,) for c in columns]

    def execute(self, sql, params):
        self.executed = (sql, params)

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _FakeConn:
    def __init__(self, rows, columns):
        self._cursor = _FakeCursor(rows, columns)

    def cursor(self):
        return self._cursor


def test_fetch_products_page_maps_rows_to_dicts_and_builds_next_cursor():
    columns = [
        "source", "source_item_id", "share_link", "name", "price",
        "discount_rate", "image_url", "category", "review_count",
        "is_all_time_low", "deal_ends_at", "updated_at",
    ]
    row = (
        "sharelink", "123", "https://toss.im/x", "상품", 1000, 60,
        "https://img", "식품", 7, False, None, None,
    )
    conn = _FakeConn(rows=[row], columns=columns)

    result = fetch_products_page(
        conn, category="식품", search=None, sort="recommend", cursor=None, limit=1
    )

    assert result["items"] == [{
        "tacaItemId": "123",
        "shareLink": "https://toss.im/x",
        "name": "상품",
        "price": 1000,
        "discountRate": 60,
        "imageUrl": "https://img",
        "category": "식품",
        "reviewCount": 7,
        "isAllTimeLow": False,
    }]
    assert result["nextCursor"] is not None  # limit(1)만큼 꽉 찼으니 다음 페이지 있음


def test_fetch_products_page_no_next_cursor_when_fewer_than_limit():
    columns = [
        "source", "source_item_id", "share_link", "name", "price",
        "discount_rate", "image_url", "category", "review_count",
        "is_all_time_low", "deal_ends_at", "updated_at",
    ]
    conn = _FakeConn(rows=[], columns=columns)

    result = fetch_products_page(
        conn, category="식품", search=None, sort="recommend", cursor=None, limit=20
    )

    assert result["items"] == []
    assert result["nextCursor"] is None


@pytest.fixture
def db_conn():
    if not os.environ.get("PRODUCTS_DB_DATABASE_URL"):
        pytest.skip("PRODUCTS_DB_DATABASE_URL not set - skipping live DB test")
    connection = psycopg2.connect(os.environ["PRODUCTS_DB_DATABASE_URL"])
    yield connection
    with connection.cursor() as cur:
        cur.execute("delete from products where source = 'test'")
    connection.commit()
    connection.close()


def test_fetch_home_products_includes_global_top_review_items_even_when_category_cutoff_excludes_them(db_conn):
    # 21개를 전부 같은 카테고리에 넣어서 카테고리별 top-20 컷오프(rn<=20)가
    # 21번째 항목을 잘라내게 만든다. review_count를 실제 운영 데이터보다
    # 훨씬 크게 잡아서(9999999대) 이 21개가 항상 전역 상위 30위 안에 들도록
    # 보장한다 - 실 운영 테이블에 어떤 데이터가 있든 이 테스트 결과가
    # 흔들리지 않는다.
    base_review_count = 9_999_999
    with db_conn.cursor() as cur:
        for i in range(21):
            cur.execute(
                """
                insert into products (
                    source, source_item_id, share_link, name, price,
                    discount_rate, image_url, category, review_count, updated_at
                ) values ('test', %s, %s, %s, 1000, 60, 'https://example.com/x.png', 'test-category', %s, now())
                """,
                (f"batch-{i}", f"https://test.example/item-{i}", f"테스트 상품 {i}", base_review_count - i),
            )
    db_conn.commit()

    items = fetch_home_products(db_conn)

    share_links = {p["shareLink"] for p in items}
    assert "https://test.example/item-20" in share_links  # 카테고리 내 21번째(최저) - 카테고리 top-20에서는 잘림
