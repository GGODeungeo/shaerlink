import os

import psycopg2
import pytest

from fetch_trending_keywords import match_products, replace_trending_keywords
from sharelink_api import _load_dotenv

_load_dotenv()


@pytest.fixture
def db_conn():
    if not os.environ.get("PRODUCTS_DB_DATABASE_URL"):
        pytest.skip("PRODUCTS_DB_DATABASE_URL not set - skipping live DB test")
    connection = psycopg2.connect(os.environ["PRODUCTS_DB_DATABASE_URL"])
    with connection.cursor() as cur:
        cur.execute(
            "insert into products "
            "(source, source_item_id, share_link, name, price, discount_rate, image_url, category, review_count) "
            "values ('test', 'tk-1', 'https://toss.im/_m/test-trending', '애슐리볶음밥 500g', 5000, 60, "
            "'https://example.com/a.png', '식품', 10)"
        )
    connection.commit()
    yield connection
    with connection.cursor() as cur:
        cur.execute("delete from trending_keywords where share_link = 'https://toss.im/_m/test-trending'")
        cur.execute("delete from products where source = 'test'")
    connection.commit()
    connection.close()


def test_match_products_keeps_keywords_found_in_catalog_and_drops_the_rest(db_conn):
    keywords = [
        {"rank": 1, "searchKeyword": "애슐리볶음밥", "searchChangePercent": 470.0},
        {"rank": 2, "searchKeyword": "존재하지않는상품명xyz", "searchChangePercent": 10.0},
    ]

    matched = match_products(db_conn, keywords)

    assert len(matched) == 1
    assert matched[0]["keyword"] == "애슐리볶음밥"
    assert matched[0]["share_link"] == "https://toss.im/_m/test-trending"


def test_replace_trending_keywords_clears_previous_snapshot(db_conn):
    stale = [{"rank": 99, "keyword": "stale", "search_change_percent": 1.0, "share_link": "https://toss.im/_m/test-trending"}]
    replace_trending_keywords(db_conn, stale)

    fresh = [{"rank": 1, "keyword": "애슐리볶음밥", "search_change_percent": 470.0, "share_link": "https://toss.im/_m/test-trending"}]
    replace_trending_keywords(db_conn, fresh)

    with db_conn.cursor() as cur:
        cur.execute("select rank, keyword from trending_keywords where share_link = 'https://toss.im/_m/test-trending'")
        rows = cur.fetchall()
    assert rows == [(1, "애슐리볶음밥")]
