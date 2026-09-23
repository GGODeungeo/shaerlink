import os

import psycopg2
import pytest

import build_app_data as bad
from build_app_data import (
    build_entry,
    build_home_subset,
    category_name,
    flag_all_time_lows,
    is_deep_discount,
    merge_unique,
    merge_with_previous,
    to_app_data,
    upsert_products,
)
from sharelink_api import _load_dotenv

_load_dotenv()  # module level - skipif below must see the real env, not a not-yet-loaded one


def _entry(share_link, category="식품", review_count=0, discount_rate=51, is_all_time_low=False, **overrides):
    # tacaItemId deliberately omitted by default - app_data entries carried
    # forward from before the tacaItemId backfill don't have one, and
    # build_home_subset must not choke on that (unlike merge_unique, which
    # keys on tacaItemId and does require it).
    entry = {
        "shareLink": share_link,
        "category": category,
        "reviewCount": review_count,
        "discountRate": discount_rate,
    }
    if is_all_time_low:
        entry["isAllTimeLow"] = True
    entry.update(overrides)
    return entry


def test_is_deep_discount_threshold():
    assert is_deep_discount({"discountRate": 49}) is False
    assert is_deep_discount({"discountRate": 50}) is False
    assert is_deep_discount({"discountRate": 51}) is True
    assert is_deep_discount({"discountRate": 90}) is True


def test_merge_unique_dedupes_by_taca_item_id_keeping_first_occurrence():
    a = [{"tacaItemId": 1, "displayName": "A"}]
    b = [{"tacaItemId": 1, "displayName": "A-dup"}, {"tacaItemId": 2, "displayName": "B"}]
    result = merge_unique(a, b)
    assert len(result) == 2
    assert next(r for r in result if r["tacaItemId"] == 1)["displayName"] == "A"


def test_category_name_resolves_matching_id_and_falls_back():
    product = {"categoryIds": [999, 5]}
    assert category_name(product, {5: ("식품", 1)}) == "식품"
    assert category_name({"categoryIds": [999]}, {5: ("식품", 1)}) == "기타"
    assert category_name({"categoryIds": []}, {5: ("식품", 1)}) == "기타"


def test_category_name_prefers_the_more_specific_deeper_category_when_ids_disagree():
    # a product cross-tagged under both an unrelated shallow branch and a
    # specific one (e.g. pilates socks tagged under "여행/취미 > 예체능레슨" as
    # well as "스포츠/레져 > 헬스/요가 > ...") should resolve to the specific one
    product = {"categoryIds": [10, 20]}
    category_map = {10: ("여행/취미", 3), 20: ("스포츠/레져", 4)}
    assert category_name(product, category_map) == "스포츠/레져"


def test_build_entry_maps_api_fields_to_app_data_fields():
    product = {
        "tacaItemId": 1,
        "displayName": "상품명",
        "displayPrice": 12000,
        "discountRate": 61,
        "thumbnailUrl": "https://x",
        "categoryIds": [5],
        "reviewCount": 342,
    }
    assert build_entry(product, {5: ("식품", 1)}) == {
        "tacaItemId": 1,
        "name": "상품명",
        "price": 12000,
        "discountRate": 61,
        "imageUrl": "https://x",
        "category": "식품",
        "reviewCount": 342,
    }


def test_build_entry_defaults_review_count_to_zero_when_missing():
    product = {
        "tacaItemId": 1,
        "displayName": "상품명",
        "displayPrice": 12000,
        "discountRate": 61,
        "thumbnailUrl": "https://x",
        "categoryIds": [],
    }
    assert build_entry(product, {})["reviewCount"] == 0


def test_build_entry_passes_through_deal_end_time_only_when_present():
    with_end_at = {
        "tacaItemId": 1, "displayName": "상품명", "displayPrice": 1000,
        "discountRate": 61, "thumbnailUrl": "https://x", "categoryIds": [],
        "endAt": "2026-09-01T23:59:59+09:00",
    }
    assert build_entry(with_end_at, {})["dealEndsAt"] == "2026-09-01T23:59:59+09:00"

    without_end_at = {
        "tacaItemId": 1, "displayName": "상품명", "displayPrice": 1000,
        "discountRate": 61, "thumbnailUrl": "https://x", "categoryIds": [],
    }
    assert "dealEndsAt" not in build_entry(without_end_at, {})


def test_to_app_data_sorts_by_discount_desc_and_skips_failed_link_issuance(monkeypatch):
    products = [
        {
            "tacaItemId": 1,
            "displayName": "낮은할인",
            "displayPrice": 1000,
            "discountRate": 55,
            "thumbnailUrl": "https://a",
            "categoryIds": [],
        },
        {
            "tacaItemId": 2,
            "displayName": "실패상품",
            "displayPrice": 1000,
            "discountRate": 99,
            "thumbnailUrl": "https://c",
            "categoryIds": [],
        },
        {
            "tacaItemId": 3,
            "displayName": "높은할인",
            "displayPrice": 2000,
            "discountRate": 80,
            "thumbnailUrl": "https://b",
            "categoryIds": [],
        },
    ]

    def fake_issue_link(token, taca_item_id, publisher_id):
        if taca_item_id == 2:
            raise RuntimeError("boom")
        return f"https://toss.im/_m/{taca_item_id}"

    monkeypatch.setattr(bad, "issue_link", fake_issue_link)

    result = to_app_data(products, {}, "publisher-id", "token", {})

    assert [r["name"] for r in result] == ["높은할인", "낮은할인"]
    assert result[0]["shareLink"] == "https://toss.im/_m/3"


def test_flag_all_time_lows_requires_a_strict_price_drop():
    data = [
        {"shareLink": "a", "price": 1000},  # ties past low -> NOT flagged (no actual drop)
        {"shareLink": "b", "price": 1000},  # beats past low -> flagged
        {"shareLink": "c", "price": 2000},  # above past low -> not flagged
        {"shareLink": "d", "price": 500},  # no history -> not flagged
    ]
    history = {"a": [1000, 1200], "b": [1500], "c": [1000]}
    flag_all_time_lows(data, history)
    assert "isAllTimeLow" not in data[0]
    assert data[1]["isAllTimeLow"] is True
    assert "isAllTimeLow" not in data[2]
    assert "isAllTimeLow" not in data[3]


def test_merge_with_previous_keeps_items_not_rediscovered_this_run():
    data = [{"shareLink": "new", "discountRate": 90}]
    previous = [
        {"shareLink": "new", "discountRate": 60},  # rediscovered - fresh data wins
        {"shareLink": "old", "discountRate": 75},  # not rediscovered - kept as last seen
    ]
    result = merge_with_previous(data, previous)
    assert [r["shareLink"] for r in result] == ["new", "old"]
    assert next(r for r in result if r["shareLink"] == "new")["discountRate"] == 90


def test_to_app_data_reuses_cached_link_instead_of_reissuing(monkeypatch):
    product = {
        "tacaItemId": 1,
        "displayName": "캐시상품",
        "displayPrice": 1000,
        "discountRate": 70,
        "thumbnailUrl": "https://a",
        "categoryIds": [],
    }

    def fail_if_called(token, taca_item_id, publisher_id):
        raise AssertionError("cached link should not be reissued")

    monkeypatch.setattr(bad, "issue_link", fail_if_called)

    link_cache = {"1": "https://toss.im/_m/cached"}
    result = to_app_data([product], {}, "publisher-id", "token", link_cache)

    assert result[0]["shareLink"] == "https://toss.im/_m/cached"


def test_build_home_subset_caps_each_category_to_pool_size():
    food = [_entry(f"food-{i}", category="식품", review_count=i) for i in range(5)]
    data = food
    result = build_home_subset(data, pool_size=3)
    assert {p["shareLink"] for p in result} == {"food-4", "food-3", "food-2"}


def test_build_home_subset_includes_all_time_low_and_carousel_pools():
    ordinary = _entry("ordinary", category="식품", discount_rate=51)
    all_time_low = _entry("cheapest-ever", category="식품", discount_rate=55, is_all_time_low=True)
    deep_discount = _entry("huge-sale", category="식품", discount_rate=90)
    data = [ordinary, all_time_low, deep_discount]

    result = build_home_subset(data, pool_size=10)

    share_links = {p["shareLink"] for p in result}
    assert share_links == {"ordinary", "cheapest-ever", "huge-sale"}


def test_build_home_subset_dedupes_by_share_link_not_taca_item_id():
    # A category-shelf pool and the all-time-low pool can both pick up the
    # same product; entries carried over from before the tacaItemId backfill
    # have no tacaItemId at all, so dedup must key on shareLink instead.
    popular_and_cheapest = _entry("dup", category="식품", review_count=100, discount_rate=55, is_all_time_low=True)
    data = [popular_and_cheapest]

    result = build_home_subset(data, pool_size=10)

    assert [p["shareLink"] for p in result] == ["dup"]


def test_build_home_subset_ignores_missing_taca_item_id():
    data = [_entry("no-id-here", category="식품", review_count=1)]
    result = build_home_subset(data, pool_size=10)
    assert result[0]["shareLink"] == "no-id-here"
    assert "tacaItemId" not in result[0]


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


def test_upsert_products_inserts_then_updates_on_conflict(db_conn):
    entry = {
        "tacaItemId": 999999,
        "shareLink": "https://toss.im/_m/test-upsert",
        "name": "테스트 상품",
        "price": 1000,
        "discountRate": 60,
        "imageUrl": "https://example.com/a.png",
        "category": "식품",
        "reviewCount": 5,
    }

    upsert_products(db_conn, [entry], source="test")

    with db_conn.cursor() as cur:
        cur.execute(
            "select name, price, review_count from products where source = 'test' and source_item_id = %s",
            (str(entry["tacaItemId"]),),
        )
        row = cur.fetchone()
    assert row == ("테스트 상품", 1000, 5)

    updated = {**entry, "price": 900, "reviewCount": 10}
    upsert_products(db_conn, [updated], source="test")

    with db_conn.cursor() as cur:
        cur.execute(
            "select count(*), price, review_count from products where source = 'test' and source_item_id = %s"
            " group by price, review_count",
            (str(entry["tacaItemId"]),),
        )
        count, price, review_count = cur.fetchone()
    assert (count, price, review_count) == (1, 900, 10)  # 새 행이 아니라 덮어써짐


def test_upsert_products_maps_optional_fields(db_conn):
    entry = {
        "tacaItemId": 999998,
        "shareLink": "https://toss.im/_m/test-optional",
        "name": "최저가 테스트",
        "price": 500,
        "discountRate": 90,
        "imageUrl": "https://example.com/b.png",
        "category": "뷰티",
        "reviewCount": 1,
        "isAllTimeLow": True,
        "dealEndsAt": "2026-12-31T23:59:59+09:00",
    }

    upsert_products(db_conn, [entry], source="test")

    with db_conn.cursor() as cur:
        cur.execute(
            "select is_all_time_low, deal_ends_at is not null from products"
            " where source = 'test' and source_item_id = %s",
            (str(entry["tacaItemId"]),),
        )
        row = cur.fetchone()
    assert row == (True, True)


def test_upsert_products_skips_entries_without_taca_item_id(db_conn):
    legacy_entry = {
        # tacaItemId 없음 - 백필 이전부터 merge_with_previous로 이어져 온 레거시 항목
        "shareLink": "https://toss.im/_m/test-no-id",
        "name": "레거시 항목",
        "price": 100,
        "discountRate": 55,
        "imageUrl": "https://example.com/c.png",
        "category": "식품",
        "reviewCount": 0,
    }

    upsert_products(db_conn, [legacy_entry], source="test")  # 에러 없이 그냥 건너뜀

    with db_conn.cursor() as cur:
        cur.execute("select count(*) from products where source = 'test'")
        count = cur.fetchone()[0]
    assert count == 0
