import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

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
# ponytail: hard cap on shipped catalog size - a 7000+ item / 2.6MB
# products.json got the mini-app rejected for a >20s first load. Data is
# already sorted by discount desc, so this just trims the long tail. Raised
# 2000 -> 4000 (~1.3MB) now that products.json is served from Vercel instead
# of slow GitHub raw - watch for load-time complaints before raising further,
# or replace this with paginated fetching if it ever needs to go much higher.
MAX_SHIPPED_ITEMS = 4000
APP_DATA_PATH = Path("app-data/products.json")
HOME_DATA_PATH = Path("app-data/products-home.json")
LINK_CACHE_PATH = Path("link_cache.json")
# Mirrors the client's own pool sizes (App.tsx SHELF_POOL_SIZE,
# TopDealsCarousel POOL_SIZE) - the home subset only needs to cover what the
# home screen actually draws from, not the full catalog.
HOME_POOL_SIZE = 20
CAROUSEL_MIN_DISCOUNT = 80
DEFAULT_SOURCE = "sharelink"


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
        "tacaItemId": product["tacaItemId"],
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


def upsert_products(conn, data: list, source: str = DEFAULT_SOURCE) -> None:
    """app_data 엔트리 리스트를 products 테이블에 upsert한다. (source,
    source_item_id) 충돌 시 UPDATE - 매일 실행되는 배치라 이게 정상 경로다.

    tacaItemId가 없는 엔트리(백필 이전부터 merge_with_previous로 계속
    이어져 온 레거시 항목)는 건너뛴다 - source_item_id가 PK라 안정적인
    값 없이는 upsert 자체가 성립하지 않는다. 새로 받아오는 항목은 항상
    tacaItemId가 있으므로 매일 이 레거시 항목 비중은 줄어든다."""
    skipped = sum(1 for entry in data if "tacaItemId" not in entry)
    if skipped:
        print(f"upsert_products: tacaItemId 없는 항목 {skipped}개 건너뜀", file=sys.stderr)

    rows = [
        (
            source,
            str(entry["tacaItemId"]),
            entry["shareLink"],
            entry["name"],
            entry["price"],
            entry["discountRate"],
            entry["imageUrl"],
            entry["category"],
            entry.get("reviewCount", 0),
            entry.get("isAllTimeLow", False),
            entry.get("dealEndsAt"),
        )
        for entry in data
        if "tacaItemId" in entry
    ]
    if not rows:
        return

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            insert into products (
                source, source_item_id, share_link, name, price,
                discount_rate, image_url, category, review_count,
                is_all_time_low, deal_ends_at, updated_at
            ) values %s
            on conflict (source, source_item_id) do update set
                share_link = excluded.share_link,
                name = excluded.name,
                price = excluded.price,
                discount_rate = excluded.discount_rate,
                image_url = excluded.image_url,
                category = excluded.category,
                review_count = excluded.review_count,
                is_all_time_low = excluded.is_all_time_low,
                deal_ends_at = excluded.deal_ends_at,
                updated_at = now()
            """,
            rows,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
        )
    conn.commit()


def merge_with_previous(data: list, previous: list) -> list:
    """Unions a partial run's results with the prior snapshot instead of
    replacing it - used when a quota cutoff meant some categories were never
    reached this run, so those items aren't dropped just for going
    unchecked. Items rediscovered this run use the fresh data; others are
    kept as last seen."""
    seen = {p["shareLink"] for p in data}
    merged = data + [p for p in previous if p["shareLink"] not in seen]
    merged.sort(key=lambda p: -p["discountRate"])
    return merged


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
    """Marks isAllTimeLow when a product's price strictly beats every price
    seen for that shareLink in prior recorded runs - a real price drop, not
    just a repeat of a price we've already seen (our history is still only
    a handful of runs deep, so an unchanged price ties the "minimum" trivially
    and isn't evidence of anything). Products with no prior history are left
    unflagged - there's nothing to compare against yet."""
    for entry in data:
        past_prices = history.get(entry["shareLink"], [])
        if past_prices and entry["price"] < min(past_prices):
            entry["isAllTimeLow"] = True


def build_home_subset(data: list, pool_size: int = HOME_POOL_SIZE) -> list:
    """Small first-paint subset for the home screen: the same top-N-by-review
    pools the client itself would slice down to per category shelf / all-time-low
    shelf / top-deals carousel, pre-trimmed server-side so the home screen
    doesn't have to wait on the full catalog to render. Order doesn't matter -
    the client re-sorts and re-shuffles everything it renders anyway."""
    by_category: dict = {}
    for p in data:
        by_category.setdefault(p["category"], []).append(p)

    pools = []
    for items in by_category.values():
        pools.append(sorted(items, key=lambda p: -p["reviewCount"])[:pool_size])

    all_time_low = [p for p in data if p.get("isAllTimeLow")]
    pools.append(sorted(all_time_low, key=lambda p: -p["reviewCount"])[:pool_size])

    carousel_pool = [p for p in data if p["discountRate"] >= CAROUSEL_MIN_DISCOUNT]
    pools.append(sorted(carousel_pool, key=lambda p: -p["reviewCount"])[:pool_size])

    # Dedupe by shareLink, not tacaItemId - app_data entries carried forward
    # across quota-cutoff runs (merge_with_previous) can predate the
    # tacaItemId backfill and not have one, but shareLink is always present.
    seen: dict = {}
    for pool in pools:
        for p in pool:
            seen.setdefault(p["shareLink"], p)
    return list(seen.values())


def main():
    # Optional: python3 build_app_data.py 1.5 caps growth at 1.5x today's
    # starting count, stopping early instead of running until the daily quota
    # is exhausted - so quota is deliberately left over for something else.
    # Omit the arg for the old unbounded (run until quota) behavior.
    growth_cap_multiplier = float(sys.argv[1]) if len(sys.argv) > 1 else None
    baseline_count = len(json.loads(APP_DATA_PATH.read_text(encoding="utf-8"))) if APP_DATA_PATH.exists() else 0
    growth_cap = int(baseline_count * growth_cap_multiplier) if growth_cap_multiplier else None

    token = get_access_token()
    category_map = get_top_level_category_map(token)

    all_products = list(get_today_deals(token))
    all_products.extend(get_best_selling_products(token))
    seen_ids = {p["tacaItemId"] for p in all_products if is_deep_discount(p)}
    quota_hit = False
    for category_id in get_category_ids(token, CATEGORY_DEPTH):
        try:
            batch = get_best_category_products(token, category_id)
        except ShareLinkAPIError as e:
            if e.error_code == "SHARELINK_OPENAPI_QUOTA_EXCEEDED":
                print("API 요청 한도 초과, 남은 카테고리 조회 중단", file=sys.stderr)
                quota_hit = True
                break
            print(f"카테고리 {category_id} 조회 실패, 건너뜀: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"카테고리 {category_id} 조회 실패, 건너뜀: {e}", file=sys.stderr)
            continue

        all_products.extend(batch)
        seen_ids.update(p["tacaItemId"] for p in batch if is_deep_discount(p))
        if growth_cap and len(seen_ids) >= growth_cap:
            print(f"목표 증가치({growth_cap}개) 도달, 남은 한도는 아껴두고 조회 중단", file=sys.stderr)
            quota_hit = True  # same partial-run handling: merge, don't prune
            break

    merged = merge_unique(all_products)
    filtered = [p for p in merged if is_deep_discount(p)]

    if not filtered:
        raise SystemExit("할인율 50% 초과 상품을 하나도 찾지 못했어요.")

    current_ids = {str(p["tacaItemId"]) for p in filtered}
    cached = load_link_cache()
    # A quota cutoff (or growth-cap stop) only means we didn't get to check
    # the remaining categories this run - not that those products are gone.
    # Pruning the cache to just this run's ids would be fine for a complete
    # run, but for a partial one it throws away still-valid links for no
    # reason.
    link_cache = cached if quota_hit else {k: v for k, v in cached.items() if k in current_ids}
    try:
        data = to_app_data(
            filtered, category_map, os.environ["SHARELINK_PUBLISHER_ID"], token, link_cache
        )
    finally:
        save_link_cache(link_cache)

    if quota_hit and APP_DATA_PATH.exists():
        previous = json.loads(APP_DATA_PATH.read_text(encoding="utf-8"))
        data = merge_with_previous(data, previous)

    flag_all_time_lows(data, load_price_history())
    data = data[:MAX_SHIPPED_ITEMS]

    APP_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_DATA_PATH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    home_data = build_home_subset(data)
    HOME_DATA_PATH.write_text(
        json.dumps(home_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    db_url = os.environ.get("PRODUCTS_DB_DATABASE_URL")
    if db_url:
        connection = psycopg2.connect(db_url)
        try:
            upsert_products(connection, data)
        finally:
            connection.close()
        print(f"완료: {APP_DATA_PATH} ({len(data)}개), {HOME_DATA_PATH} ({len(home_data)}개), DB upsert ({len(data)}개)")
    else:
        print(f"완료: {APP_DATA_PATH} ({len(data)}개 상품), {HOME_DATA_PATH} ({len(home_data)}개 상품) - PRODUCTS_DB_DATABASE_URL 없어서 DB는 건너뜀")


if __name__ == "__main__":
    main()
