import json
import os
from pathlib import Path

from sharelink_api import (
    get_access_token,
    get_best_category_products,
    get_today_deals,
    get_top_level_category_ids,
    get_top_level_category_map,
    issue_link,
)

MIN_DISCOUNT = 50
APP_DATA_PATH = Path("app-data/products.json")


def is_deep_discount(product: dict) -> bool:
    return product["discountRate"] >= MIN_DISCOUNT


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


def to_app_data(products: list, category_map: dict, publisher_id: str, token: str) -> list:
    slim = []
    for p in products:
        slim.append(
            {
                "name": p["displayName"],
                "price": p["displayPrice"],
                "discountRate": p["discountRate"],
                "imageUrl": p["thumbnailUrl"],
                "category": category_name(p, category_map),
                "shareLink": issue_link(token, p["tacaItemId"], publisher_id),
            }
        )
    slim.sort(key=lambda p: -p["discountRate"])
    return slim


def main():
    token = get_access_token()
    category_map = get_top_level_category_map(token)

    all_products = list(get_today_deals(token))
    for category_id in get_top_level_category_ids(token):
        all_products.extend(get_best_category_products(token, category_id))

    merged = merge_unique(all_products)
    filtered = [p for p in merged if is_deep_discount(p)]

    if not filtered:
        raise SystemExit("할인율 50% 이상 상품을 하나도 찾지 못했어요.")

    data = to_app_data(filtered, category_map, os.environ["SHARELINK_PUBLISHER_ID"], token)

    APP_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {APP_DATA_PATH} ({len(data)}개 상품)")


if __name__ == "__main__":
    main()
