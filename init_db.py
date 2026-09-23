"""Products 테이블 스키마를 생성한다. 마이그레이션 프레임워크 없이 수동
DDL 한 번 - 재실행해도 안전하도록 전부 IF NOT EXISTS."""
import os

import psycopg2

DDL_STATEMENTS = [
    "create extension if not exists pg_trgm",
    """
    create table if not exists products (
        source          text not null,
        source_item_id  text not null,
        share_link      text not null,
        name            text not null,
        price           integer not null,
        discount_rate   integer not null,
        image_url       text not null,
        category        text not null,
        review_count    integer not null default 0,
        is_all_time_low boolean not null default false,
        deal_ends_at    timestamptz,
        updated_at      timestamptz not null default now(),
        primary key (source, source_item_id)
    )
    """,
    "create index if not exists products_category_idx on products (category)",
    """
    create index if not exists products_name_trgm_idx
        on products using gin (name gin_trgm_ops)
    """,
    """
    create index if not exists products_review_count_idx
        on products (review_count desc)
    """,
]


def init_db(conn) -> None:
    with conn.cursor() as cur:
        for statement in DDL_STATEMENTS:
            cur.execute(statement)
    conn.commit()


if __name__ == "__main__":
    from sharelink_api import _load_dotenv

    _load_dotenv()
    connection = psycopg2.connect(os.environ["PRODUCTS_DB_DATABASE_URL"])
    try:
        init_db(connection)
        print("완료: products 테이블/인덱스 생성(또는 이미 존재함)")
    finally:
        connection.close()
