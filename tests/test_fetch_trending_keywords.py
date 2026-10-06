import os

import psycopg2
import pytest

import build_app_data as bad
import fetch_trending_keywords as ftk
from fetch_trending_keywords import replace_trending_keywords, top_selling_entries
from sharelink_api import _load_dotenv

_load_dotenv()


@pytest.fixture
def db_conn():
    if not os.environ.get("PRODUCTS_DB_DATABASE_URL"):
        pytest.skip("PRODUCTS_DB_DATABASE_URL not set - skipping live DB test")
    connection = psycopg2.connect(os.environ["PRODUCTS_DB_DATABASE_URL"])
    yield connection
    connection.close()


def test_top_selling_entries_keeps_api_rank_order_and_drops_non_deep_discount(monkeypatch):
    products = [
        {"tacaItemId": 1, "displayName": "저할인", "displayPrice": 1000, "discountRate": 40, "thumbnailUrl": "https://a", "categoryIds": []},
        {"tacaItemId": 2, "displayName": "1등", "displayPrice": 2000, "discountRate": 70, "thumbnailUrl": "https://b", "categoryIds": []},
        {"tacaItemId": 3, "displayName": "2등", "displayPrice": 3000, "discountRate": 60, "thumbnailUrl": "https://c", "categoryIds": []},
    ]
    monkeypatch.setattr(ftk, "get_top_level_category_map", lambda token: {})
    monkeypatch.setattr(ftk, "get_best_selling_products", lambda token: products)
    monkeypatch.setattr(ftk, "load_link_cache", lambda: {})
    monkeypatch.setattr(ftk, "save_link_cache", lambda cache: None)
    monkeypatch.setattr(bad, "issue_link", lambda token, taca_item_id, publisher_id: f"https://toss.im/_m/{taca_item_id}")
    monkeypatch.setenv("SHARELINK_PUBLISHER_ID", "pub-1")

    entries = top_selling_entries("token", limit=15)

    # order is the best-selling API's own order, not re-sorted by discount -
    # and the 40%-off item is dropped since it's not a deep discount
    assert [e["name"] for e in entries] == ["1등", "2등"]


def test_top_selling_entries_respects_limit_after_filtering(monkeypatch):
    products = [
        {"tacaItemId": i, "displayName": f"상품{i}", "displayPrice": 1000, "discountRate": 60, "thumbnailUrl": "https://a", "categoryIds": []}
        for i in range(1, 6)
    ]
    monkeypatch.setattr(ftk, "get_top_level_category_map", lambda token: {})
    monkeypatch.setattr(ftk, "get_best_selling_products", lambda token: products)
    monkeypatch.setattr(ftk, "load_link_cache", lambda: {})
    monkeypatch.setattr(ftk, "save_link_cache", lambda cache: None)
    monkeypatch.setattr(bad, "issue_link", lambda token, taca_item_id, publisher_id: f"https://toss.im/_m/{taca_item_id}")
    monkeypatch.setenv("SHARELINK_PUBLISHER_ID", "pub-1")

    entries = top_selling_entries("token", limit=3)

    assert [e["name"] for e in entries] == ["상품1", "상품2", "상품3"]


def test_replace_trending_keywords_clears_previous_snapshot(db_conn):
    """replace_trending_keywords는 테이블 전체를 delete+insert하므로(실서비스에서
    의도된 동작) 운영 DB에 직접 돌리는 이 테스트는 반드시 기존 내용을
    스냅샷/복원해야 한다 - 안 그러면 테스트가 실제 트렌드 데이터를 지워버린다
    (한 번 그래서 운영 데이터가 날아간 적 있음)."""
    with db_conn.cursor() as cur:
        cur.execute("select rank, keyword, search_change_percent, share_link from trending_keywords")
        original_rows = cur.fetchall()

    try:
        stale = [{"name": "stale", "shareLink": "https://toss.im/_m/test-trending"}]
        replace_trending_keywords(db_conn, stale)

        fresh = [{"name": "애슐리볶음밥", "shareLink": "https://toss.im/_m/test-trending"}]
        replace_trending_keywords(db_conn, fresh)

        with db_conn.cursor() as cur:
            cur.execute("select rank, keyword from trending_keywords where share_link = 'https://toss.im/_m/test-trending'")
            rows = cur.fetchall()
        assert rows == [(1, "애슐리볶음밥")]
    finally:
        with db_conn.cursor() as cur:
            cur.execute("delete from trending_keywords")
            for row in original_rows:
                cur.execute(
                    "insert into trending_keywords (rank, keyword, search_change_percent, share_link) "
                    "values (%s, %s, %s, %s)",
                    row,
                )
        db_conn.commit()
