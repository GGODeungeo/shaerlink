import json
import os
import subprocess
import sys
from pathlib import Path

from sharelink_api import (
    ShareLinkAPIError,
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
    """Products are sometimes tagged with categoryIds across unrelated
    top-level sections (e.g. pilates socks under both 스포츠/레져 and the
    여행/취미 > 예체능레슨 hobby-lessons branch) - prefer whichever tagged
    categoryId is the most specific (deepest) rather than just the first
    one listed, since depth correlates with how well-targeted the tag is."""
    matches = [category_map[cid] for cid in product.get("categoryIds", []) if cid in category_map]
    if not matches:
        return "기타"
    root_name, _ = max(matches, key=lambda root_and_depth: root_and_depth[1])
    return root_name


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


def load_price_history(path: str = str(APP_DATA_PATH)) -> dict:
    """Mines this file's own git history for a per-shareLink price timeline
    - one data point per day this pipeline has run and committed, no extra
    storage needed.
    ponytail: re-walks and re-parses the full history every run (O(days
    elapsed) `git show` + json.loads calls). Fine for the history depth
    this app accumulates over weeks/months; if it ever grows to years of
    daily commits, cache the running per-shareLink minimum to a side file
    and only fold in commits newer than the last run."""
    try:
        commits = subprocess.run(
            ["git", "log", "--format=%H", "--", path],
            capture_output=True, text=True, check=True,
        ).stdout.split()
    except subprocess.CalledProcessError:
        return {}

    history: dict = {}
    for commit in reversed(commits):
        result = subprocess.run(["git", "show", f"{commit}:{path}"], capture_output=True, text=True)
        if result.returncode != 0:
            continue
        try:
            snapshot = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        for p in snapshot:
            history.setdefault(p["shareLink"], []).append(p["price"])
    return history


def flag_all_time_lows(data: list, history: dict) -> None:
    """Marks isAllTimeLow when a product's price matches or beats every
    price seen for that shareLink in prior recorded runs. Products with no
    prior history are left unflagged - there's nothing to compare against
    yet, so claiming "all-time low" would be meaningless."""
    for entry in data:
        past_prices = history.get(entry["shareLink"], [])
        if past_prices and entry["price"] <= min(past_prices):
            entry["isAllTimeLow"] = True


def main():
    token = get_access_token()
    category_map = get_top_level_category_map(token)

    all_products = list(get_today_deals(token))
    all_products.extend(get_best_selling_products(token))
    for category_id in get_category_ids(token, CATEGORY_DEPTH):
        try:
            all_products.extend(get_best_category_products(token, category_id))
        except ShareLinkAPIError as e:
            if e.error_code == "SHARELINK_OPENAPI_QUOTA_EXCEEDED":
                print("API 요청 한도 초과, 남은 카테고리 조회 중단", file=sys.stderr)
                break
            print(f"카테고리 {category_id} 조회 실패, 건너뜀: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"카테고리 {category_id} 조회 실패, 건너뜀: {e}", file=sys.stderr)
            continue

    merged = merge_unique(all_products)
    filtered = [p for p in merged if is_deep_discount(p)]

    if not filtered:
        raise SystemExit("할인율 50% 초과 상품을 하나도 찾지 못했어요.")

    current_ids = {str(p["tacaItemId"]) for p in filtered}
    link_cache = {k: v for k, v in load_link_cache().items() if k in current_ids}
    try:
        data = to_app_data(
            filtered, category_map, os.environ["SHARELINK_PUBLISHER_ID"], token, link_cache
        )
    finally:
        save_link_cache(link_cache)

    flag_all_time_lows(data, load_price_history())

    APP_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {APP_DATA_PATH} ({len(data)}개 상품)")


if __name__ == "__main__":
    main()
