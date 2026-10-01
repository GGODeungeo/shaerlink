"""토스비즈니스 "토스 앱으로 이 상품을 찾아요"(검색 급상승 키워드) 스냅샷을
받아와서, 우리 카탈로그(products)와 이름이 매칭되는 것만 trending_keywords에
채워 넣는다. 대부분의 키워드는 우리가 안 파는 상품이라 버려진다 - 그게 정상.

비공식 내부 API라 세션 쿠키 인증이고, 쿠키는 만료되면 수동으로 다시 넣어야
한다(TOSS_BUSINESS_COOKIE). 자동 스케줄 없이 수동/로컬 실행 전용.

실행: python3 fetch_trending_keywords.py
"""
import json
import os
import urllib.request

import psycopg2

from sharelink_api import _load_dotenv

BLUE_OCEAN_URL = "https://business-accounts.toss.im/shopping/blue-ocean-products"
GROUP_ID = "1002971"


def fetch_keywords() -> list:
    cookie = os.environ["TOSS_BUSINESS_COOKIE"]
    req = urllib.request.Request(
        f"{BLUE_OCEAN_URL}?groupId={GROUP_ID}",
        headers={"Cookie": cookie, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read())
    if body.get("resultType") != "SUCCESS":
        raise RuntimeError(f"blue-ocean-products 호출 실패: {body}")
    return body["success"]


def match_products(conn, keywords: list) -> list:
    """키워드별로 가장 리뷰 많은 매칭 상품 하나를 고른다. 매칭 없는
    키워드는 조용히 버린다(트렌드 키워드 대부분이 우리 카탈로그 밖임)."""
    matched = []
    with conn.cursor() as cur:
        for entry in keywords:
            cur.execute(
                "select share_link from products where name ilike %s "
                "order by review_count desc limit 1",
                (f"%{entry['searchKeyword']}%",),
            )
            row = cur.fetchone()
            if row is None:
                continue
            matched.append({
                "rank": entry["rank"],
                "keyword": entry["searchKeyword"],
                "search_change_percent": entry["searchChangePercent"],
                "share_link": row[0],
            })
    return matched


def replace_trending_keywords(conn, matched: list) -> None:
    with conn.cursor() as cur:
        cur.execute("delete from trending_keywords")
        for item in matched:
            cur.execute(
                "insert into trending_keywords (rank, keyword, search_change_percent, share_link) "
                "values (%s, %s, %s, %s)",
                (item["rank"], item["keyword"], item["search_change_percent"], item["share_link"]),
            )
    conn.commit()


def main():
    _load_dotenv()
    keywords = fetch_keywords()
    print(f"키워드 {len(keywords)}개 수신")

    conn = psycopg2.connect(os.environ["PRODUCTS_DB_DATABASE_URL"])
    try:
        matched = match_products(conn, keywords)
        print(f"카탈로그 매칭: {len(matched)}개")
        for item in matched:
            print(f"  {item['rank']:>3}. {item['keyword']} ({item['search_change_percent']}%)")
        replace_trending_keywords(conn, matched)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
