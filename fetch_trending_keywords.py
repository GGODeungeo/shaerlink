"""ShareLink 공식 베스트셀러 API 순위를 그대로 "요즘 많이 찾는 상품"으로
보여준다. 예전엔 토스비즈니스 대시보드의 "검색 급상승 키워드"(비공식 API,
세션 쿠키 인증)를 우리 카탈로그와 이름 매칭해서 썼는데, 검색량 급등이 실제
판매와 무관한 경우가 많아(예: 스와로브스키 검색 ▲4950%) 오해를 줬다. 이제는
공식 베스트셀러 API가 내려주는 순서를 그대로 쓴다 - 매칭/추정 없이 정확하다.

이 앱 자체가 딥디스카운트 전용이라(그 외 상품은 둘러보기/검색에도 안 뜬다)
베스트셀러 중에서도 딥디스카운트(discountRate > 50)인 것만 추린다.

ShareLink API는 IP 허용목록이 있어 고정 IP(로컬/VPS)에서만 호출 가능하다
(build_app_data.py와 동일 제약) - 그래서 GitHub Actions 크론은 꺼두고
수동/로컬 실행 전용으로 돌린다.

실행: python3 fetch_trending_keywords.py
"""
import os
import sys

import psycopg2

from build_app_data import (
    build_entry_with_link,
    is_deep_discount,
    load_link_cache,
    save_link_cache,
    upsert_products,
)
from sharelink_api import (
    _load_dotenv,
    get_access_token,
    get_best_selling_products,
    get_top_level_category_map,
)

LIMIT = 15


def top_selling_entries(token: str, limit: int = LIMIT) -> list:
    """베스트셀러 API가 판매량순으로 내려주는 리스트에서 딥디스카운트
    상품만 순서 그대로 추려 순위로 쓴다."""
    category_map = get_top_level_category_map(token)
    link_cache = load_link_cache()
    publisher_id = os.environ["SHARELINK_PUBLISHER_ID"]
    best_selling = [p for p in get_best_selling_products(token) if is_deep_discount(p)][:limit]
    try:
        entries = [
            entry
            for p in best_selling
            if (entry := build_entry_with_link(p, category_map, token, publisher_id, link_cache))
        ]
    finally:
        save_link_cache(link_cache)
    return entries


def replace_trending_keywords(conn, entries: list) -> None:
    """trending_keywords를 전체 delete+insert한다(실서비스에서 의도된
    동작) - 매번 오늘의 순위로 통째로 갈아치운다.
    ponytail: search_change_percent는 더 이상 의미 있는 값이 없어(순위가
    검색량 급등이 아니라 판매 순위라서) 0을 넣는다 - UI도 더는 표시하지
    않는다. 컬럼 자체를 지우려면 schema migration이 필요해 보류."""
    with conn.cursor() as cur:
        cur.execute("delete from trending_keywords")
        for rank, entry in enumerate(entries, start=1):
            cur.execute(
                "insert into trending_keywords (rank, keyword, search_change_percent, share_link) "
                "values (%s, %s, %s, %s)",
                (rank, entry["name"], 0, entry["shareLink"]),
            )
    conn.commit()


def main():
    _load_dotenv()
    token = get_access_token()
    entries = top_selling_entries(token)
    print(f"베스트셀러(딥디스카운트) {len(entries)}개 수신")
    for i, e in enumerate(entries, start=1):
        print(f"  {i:>2}. {e['name']}")

    if not entries:
        print("추려진 상품이 하나도 없어요 - trending_keywords를 비우지 않고 종료", file=sys.stderr)
        return

    conn = psycopg2.connect(os.environ["PRODUCTS_DB_DATABASE_URL"])
    try:
        upsert_products(conn, entries)
        replace_trending_keywords(conn, entries)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
