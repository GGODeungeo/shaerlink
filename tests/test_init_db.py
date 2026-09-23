import os

import psycopg2
import pytest

from init_db import init_db
from sharelink_api import _load_dotenv

_load_dotenv()  # .env not loaded yet at collection time otherwise - skipif below would misfire

pytestmark = pytest.mark.skipif(
    not os.environ.get("PRODUCTS_DB_DATABASE_URL"),
    reason="PRODUCTS_DB_DATABASE_URL not set - skipping live DB test",
)


@pytest.fixture
def conn():
    connection = psycopg2.connect(os.environ["PRODUCTS_DB_DATABASE_URL"])
    yield connection
    connection.close()


def test_init_db_is_idempotent(conn):
    init_db(conn)
    init_db(conn)  # 두 번째 실행도 에러 없이 통과해야 함

    with conn.cursor() as cur:
        cur.execute(
            "select column_name from information_schema.columns where table_name = 'products'"
        )
        columns = {row[0] for row in cur.fetchall()}

    assert columns == {
        "source", "source_item_id", "share_link", "name", "price",
        "discount_rate", "image_url", "category", "review_count",
        "is_all_time_low", "deal_ends_at", "updated_at",
    }
