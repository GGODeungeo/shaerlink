import json
import sys
from datetime import date
from pathlib import Path

from scrape import run_scrape

MIN_DISCOUNT = 50
PROFILE_DIR = "browser-profile"
APP_DATA_PATH = Path("app-data/products.json")


def is_deep_discount(product: dict) -> bool:
    return product["discountRate"] >= MIN_DISCOUNT


def to_app_data(products: list) -> list:
    slim = [
        {
            "name": p["name"],
            "price": p["price"],
            "discountRate": p["discountRate"],
            "imageUrl": p["imageUrl"],
            "shareLink": p["shareLink"],
        }
        for p in products
    ]
    slim.sort(key=lambda p: -p["discountRate"])
    return slim


def main():
    today = date.today().isoformat()
    output_dir = Path("output") / today

    try:
        products = run_scrape(
            PROFILE_DIR, output_dir, filter_fn=lambda ps: [p for p in ps if is_deep_discount(p)]
        )
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    data = to_app_data(products)
    APP_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {APP_DATA_PATH} ({len(data)}개 상품)")


if __name__ == "__main__":
    main()
