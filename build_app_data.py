import json
import os
import sys
from pathlib import Path

from sharelink_api import (
    get_access_token,
    get_best_category_products,
    get_best_selling_products,
    get_category_meta_map,
    get_today_deals,
    get_top_level_category_ids,
    get_top_level_category_map,
    issue_link,
)

MIN_DISCOUNT = 50
APP_DATA_PATH = Path("app-data/products.json")


def is_deep_discount(product: dict) -> bool:
    return product["discountRate"] > MIN_DISCOUNT


def merge_unique(*item_lists: list) -> list:
    seen = {}
    for items in item_lists:
        for item in items:
            seen.setdefault(item["tacaItemId"], item)
    return list(seen.values())


def category_name(product: dict, category_map: dict) -> str:
    for category_id in product.get("categoryIds", []):
        if category_id in category_map:
            return category_map[category_id]
    return "기타"


def deepest_category_id(product: dict, category_meta: dict):
    """The most specific (deepest-level) categoryId a product is tagged
    under, e.g. '국산생수' rather than the broad '식품' root - used to scope
    rank badges narrowly. Returns None if no tagged id is known."""
    known = [c for c in product.get("categoryIds", []) if c in category_meta]
    if not known:
        return None
    return max(known, key=lambda c: category_meta[c]["level"])


def build_entry(product: dict, category_map: dict, rank_badges: dict) -> dict:
    entry = {
        "name": product["displayName"],
        "price": product["displayPrice"],
        "discountRate": product["discountRate"],
        "imageUrl": product["thumbnailUrl"],
        "category": category_name(product, category_map),
        "reviewCount": product.get("reviewCount", 0),
    }
    badge = rank_badges.get(product["tacaItemId"])
    if badge is not None:
        label, rank = badge
        if rank <= 10:
            entry["rankCategory"] = label
            entry["categoryRank"] = rank
    return entry


def to_app_data(
    products: list, category_map: dict, rank_badges: dict, publisher_id: str, token: str
) -> list:
    slim = []
    for p in products:
        entry = build_entry(p, category_map, rank_badges)
        try:
            entry["shareLink"] = issue_link(token, p["tacaItemId"], publisher_id)
        except Exception as e:
            print(f"링크 발급 실패, 건너뜀: {entry['name']} ({e})", file=sys.stderr)
            continue
        slim.append(entry)
    slim.sort(key=lambda p: -p["discountRate"])
    return slim


def main():
    token = get_access_token()
    category_map = get_top_level_category_map(token)
    category_meta = get_category_meta_map(token)

    root_category_lists = [
        get_best_category_products(token, category_id)
        for category_id in get_top_level_category_ids(token)
    ]

    all_products = list(get_today_deals(token))
    all_products.extend(get_best_selling_products(token))
    for items in root_category_lists:
        all_products.extend(items)

    merged = merge_unique(all_products)
    filtered = [p for p in merged if is_deep_discount(p)]

    if not filtered:
        raise SystemExit("할인율 50% 초과 상품을 하나도 찾지 못했어요.")

    specific_ids = {
        cid
        for cid in (deepest_category_id(p, category_meta) for p in filtered)
        if cid is not None
    }
    rank_badges = {}
    for category_id in specific_ids:
        label = category_meta[category_id]["displayName"]
        for item in get_best_category_products(token, category_id):
            rank_badges.setdefault(item["tacaItemId"], (label, item["rank"]))

    data = to_app_data(
        filtered, category_map, rank_badges, os.environ["SHARELINK_PUBLISHER_ID"], token
    )

    APP_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {APP_DATA_PATH} ({len(data)}개 상품)")


if __name__ == "__main__":
    main()
