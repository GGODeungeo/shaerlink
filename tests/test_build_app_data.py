import build_app_data as bad
from build_app_data import (
    build_entry,
    category_name,
    flag_all_time_lows,
    is_deep_discount,
    merge_unique,
    to_app_data,
)


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


def test_flag_all_time_lows_marks_price_at_or_below_every_past_price():
    data = [
        {"shareLink": "a", "price": 1000},  # ties past low -> flagged
        {"shareLink": "b", "price": 1000},  # beats past low -> flagged
        {"shareLink": "c", "price": 2000},  # above past low -> not flagged
        {"shareLink": "d", "price": 500},  # no history -> not flagged
    ]
    history = {"a": [1000, 1200], "b": [1500], "c": [1000]}
    flag_all_time_lows(data, history)
    assert data[0]["isAllTimeLow"] is True
    assert data[1]["isAllTimeLow"] is True
    assert "isAllTimeLow" not in data[2]
    assert "isAllTimeLow" not in data[3]


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
