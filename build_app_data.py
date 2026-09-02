import json
import os
import sys
from pathlib import Path

from sharelink_api import (
    get_access_token,
    get_best_category_products,
    get_best_selling_products,
    get_category_ids,
    get_today_deals,
    get_top_level_category_map,
    issue_link,
)

MIN_DISCOUNT = 50
CATEGORY_DEPTH = 3
APP_DATA_PATH = Path("app-data/products.json")
LINK_CACHE_PATH = Path("link_cache.json")


def load_link_cache() -> dict:
    if not LINK_CACHE_PATH.exists():
        return {}
    return json.loads(LINK_CACHE_PATH.read_text(encoding="utf-8"))


def save_link_cache(cache: dict) -> None:
    LINK_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


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


def build_entry(product: dict, category_map: dict) -> dict:
    entry = {
        "name": product["displayName"],
        "price": product["displayPrice"],
        "discountRate": product["discountRate"],
        "imageUrl": product["thumbnailUrl"],
        "category": category_name(product, category_map),
        "reviewCount": product.get("reviewCount", 0),
    }
    if "endAt" in product:
        entry["dealEndsAt"] = product["endAt"]
    return entry


def to_app_data(
    products: list, category_map: dict, publisher_id: str, token: str, link_cache: dict
) -> list:
    slim = []
    for p in products:
        entry = build_entry(p, category_map)
        taca_id = str(p["tacaItemId"])
        share_link = link_cache.get(taca_id)
        if share_link is None:
            try:
                share_link = issue_link(token, p["tacaItemId"], publisher_id)
            except Exception as e:
                print(f"링크 발급 실패, 건너뜀: {entry['name']} ({e})", file=sys.stderr)
                continue
            link_cache[taca_id] = share_link
        entry["shareLink"] = share_link
        slim.append(entry)
    slim.sort(key=lambda p: -p["discountRate"])
    return slim


def main():
    token = get_access_token()
    category_map = get_top_level_category_map(token)

    all_products = list(get_today_deals(token))
    all_products.extend(get_best_selling_products(token))
    for category_id in get_category_ids(token, CATEGORY_DEPTH):
        try:
            all_products.extend(get_best_category_products(token, category_id))
        except Exception as e:
            print(f"카테고리 {category_id} 조회 실패, 건너뜀: {e}", file=sys.stderr)
            continue

    merged = merge_unique(all_products)
    filtered = [p for p in merged if is_deep_discount(p)]

    if not filtered:
        raise SystemExit("할인율 50% 초과 상품을 하나도 찾지 못했어요.")

    link_cache = load_link_cache()
    try:
        data = to_app_data(
            filtered, category_map, os.environ["SHARELINK_PUBLISHER_ID"], token, link_cache
        )
    finally:
        save_link_cache(link_cache)

    APP_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {APP_DATA_PATH} ({len(data)}개 상품)")


if __name__ == "__main__":
    main()
