import build_app_data as bad
from build_app_data import (
    build_entry,
    category_name,
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


def test_category_name_resolves_first_matching_id_and_falls_back():
    product = {"categoryIds": [999, 5, 6]}
    assert category_name(product, {5: "식품"}) == "식품"
    assert category_name({"categoryIds": [999]}, {5: "식품"}) == "기타"
    assert category_name({"categoryIds": []}, {5: "식품"}) == "기타"


def test_build_entry_maps_api_fields_to_app_data_fields():
    product = {
        "displayName": "상품명",
        "displayPrice": 12000,
        "discountRate": 61,
        "thumbnailUrl": "https://x",
        "categoryIds": [5],
        "reviewCount": 342,
    }
    assert build_entry(product, {5: "식품"}) == {
        "name": "상품명",
        "price": 12000,
        "discountRate": 61,
        "imageUrl": "https://x",
        "category": "식품",
        "reviewCount": 342,
    }


def test_build_entry_defaults_review_count_to_zero_when_missing():
    product = {
        "displayName": "상품명",
        "displayPrice": 12000,
        "discountRate": 61,
        "thumbnailUrl": "https://x",
        "categoryIds": [],
    }
    assert build_entry(product, {})["reviewCount"] == 0


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

    result = to_app_data(products, {}, "publisher-id", "token")

    assert [r["name"] for r in result] == ["높은할인", "낮은할인"]
    assert result[0]["shareLink"] == "https://toss.im/_m/3"
