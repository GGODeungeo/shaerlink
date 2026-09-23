# 상품 카탈로그 DB 전환 — 1단계 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상품 데이터를 Postgres(Neon)에 upsert하고, 홈/카테고리/검색용 쿼리 API 3종을 `api/webhook.py`에 추가한다. 화면(App.tsx)과 기존 `/api/products`(전체 덤프)는 이번 단계에서 그대로 둔다 — 이 단계가 끝나도 겉으로 보이는 앱 동작은 무변화다.

**Architecture:** `build_app_data.py`는 지금처럼 쉐어링크 API에서 데이터를 모은 뒤, 기존 JSON 파일 쓰기에 **더해** Postgres에 upsert한다(파일도 계속 써야 기존 `/api/products` 전체 덤프가 안 죽는다 — 스펙 원문은 "JSON 대신 DB"라고 했지만 1단계에서 구 엔드포인트를 살려두려면 파일도 같이 갱신해야 해서, 이 계획은 "교체"가 아니라 "병행 쓰기"로 간다). `api/webhook.py`는 새 GET 라우트 3개(`/api/products/home`, `/api/products?category=`, `/api/products?search=`)를 추가해 DB를 직접 쿼리한다. 두 파일 모두 psycopg2로 각자 독립적으로 접속한다(공용 모듈 없음 — `api/webhook.py`가 저장소 루트 모듈을 import하는 게 Vercel 서버리스 환경에서 보장되는지 불확실해서, 지금 `sharelink_api.py`를 안 쓰고 자체완결형으로 짜여 있는 기존 관례를 그대로 따른다).

**Tech Stack:** Python 3.9+, psycopg2-binary, Postgres(Neon), pytest

**Spec:** `docs/superpowers/specs/2026-09-23-product-catalog-db-migration-design.md`

## Global Constraints

- DB 접속 문자열은 환경변수 `PRODUCTS_DB_DATABASE_URL`에서 읽는다 (Vercel Neon 연동이 Production/Preview에 자동 주입 완료됨)
- 마이그레이션 프레임워크 없음 — 스키마는 `init_db.py`의 수동 DDL 한 번으로 생성(재실행해도 안전하게 `IF NOT EXISTS` 사용)
- `sort` 파라미터는 클라이언트의 기존 `SORT_OPTIONS`와 동일하게 3종만 지원: `recommend`(review_count desc) / `discount`(discount_rate desc) / `price`(price asc)
- 검색은 pg_trgm 인덱스를 쓰되 매칭 로직 자체는 클라이언트의 기존 동작(`name.includes(검색어)`, 대소문자 무시)과 동일한 **부분 문자열 포함**으로 — 유사도 랭킹 아님
- 커서 페이지네이션은 OFFSET 방식 금지 — keyset 방식만 사용. 정렬 컬럼 + `(source, source_item_id)`를 **같은 방향**으로 묶어서 튜플 비교한다(방향이 섞이면 튜플 비교가 깨짐)
- 이번 단계에서 `App.tsx`, `/api/products`(전체 덤프) 라우트, `products.json`/`products-home.json` 파일 자체는 손대지 않는다(계속 존재·갱신됨)

---

### Task 1: DB 접속 준비 + psycopg2 의존성

**Files:**
- Modify: `requirements.txt`
- Modify: `.env` (로컬 전용, git에 커밋 안 됨 — `.gitignore`에 이미 `.env` 포함돼 있음)

**Interfaces:**
- Produces: 로컬 환경에서 `os.environ["PRODUCTS_DB_DATABASE_URL"]`로 접속 가능한 상태, `import psycopg2`가 동작하는 상태

- [ ] **Step 1: `requirements.txt`에 psycopg2-binary 추가**

`requirements.txt` 전체 내용을 아래로 교체:

```
pytest
psycopg2-binary
```

- [ ] **Step 2: 설치**

Run: `pip install -r requirements.txt`
Expected: `psycopg2-binary`가 정상 설치됨 (에러 없이 끝남)

- [ ] **Step 3: Vercel에서 DB 접속 문자열을 로컬로 가져오기**

Vercel CLI가 없으면 먼저 로그인:

Run: `npx vercel login`
(브라우저로 인증 — 이 프로젝트 소유자 계정으로 로그인)

로그인 후 프로젝트와 연결하고 환경변수를 받아온다:

Run: `npx vercel link --yes` (처음 한 번, `toss-shaerlink/shaerlink` 프로젝트 선택)
Run: `npx vercel env pull .env.vercel`

Expected: `.env.vercel` 파일이 생성되고 그 안에 `PRODUCTS_DB_DATABASE_URL=...`이 포함됨. **이 파일 내용을 터미널에 출력하거나 채팅에 붙여넣지 않는다** — 값 자체는 열어볼 필요 없이 다음 단계에서 바로 로드해서 쓴다.

- [ ] **Step 4: `.env.vercel`을 `.gitignore`에 추가(아직 없다면)**

`.gitignore`에 다음 줄이 없으면 추가:
```
.env.vercel
```

- [ ] **Step 5: `.env`에 병합**

Run:
```bash
grep '^PRODUCTS_DB_DATABASE_URL=' .env.vercel >> .env
```
Expected: `.env`에 `PRODUCTS_DB_DATABASE_URL=...` 한 줄이 추가됨 (다른 스크립트들이 이미 `.env`를 로드하는 관례를 그대로 따름 — `sharelink_api.py`의 `_load_dotenv()`가 `build_app_data.py` import 시점에 자동으로 읽음)

- [ ] **Step 6: 접속 확인**

Run:
```bash
python3 -c "
import os
from sharelink_api import _load_dotenv
_load_dotenv()
import psycopg2
conn = psycopg2.connect(os.environ['PRODUCTS_DB_DATABASE_URL'])
cur = conn.cursor()
cur.execute('SELECT 1')
print('OK:', cur.fetchone())
conn.close()
"
```
Expected: `OK: (1,)` 출력

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore
git commit -m "Add psycopg2-binary dependency for the product-catalog DB"
```
(`.env`/`.env.vercel`은 커밋 대상 아님 — `.gitignore`로 제외됨)

---

### Task 2: 스키마 생성 (`init_db.py`)

**Files:**
- Create: `init_db.py`
- Test: `tests/test_init_db.py`

**Interfaces:**
- Produces: `DDL_STATEMENTS: list[str]` (모듈 상수), `init_db(conn) -> None` 함수
- Consumes: 없음 (psycopg2 connection 객체만 인자로 받음)

- [ ] **Step 1: `init_db.py` 작성**

```python
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
```

- [ ] **Step 2: 테스트 작성 — 실제 DB에 대해 두 번 실행해도 안전한지 확인**

`tests/test_init_db.py`:

```python
import os

import psycopg2
import pytest

from init_db import init_db

pytestmark = pytest.mark.skipif(
    not os.environ.get("PRODUCTS_DB_DATABASE_URL"),
    reason="PRODUCTS_DB_DATABASE_URL not set - skipping live DB test",
)


@pytest.fixture
def conn():
    from sharelink_api import _load_dotenv

    _load_dotenv()
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
```

- [ ] **Step 3: 실제 DB에 스키마 생성**

Run: `python3 init_db.py`
Expected: `완료: products 테이블/인덱스 생성(또는 이미 존재함)`

- [ ] **Step 4: 테스트 실행**

Run: `python3 -m pytest tests/test_init_db.py -v`
Expected: `test_init_db_is_idempotent PASSED`

- [ ] **Step 5: Commit**

```bash
git add init_db.py tests/test_init_db.py
git commit -m "Add products table schema (init_db.py)"
```

---

### Task 3: `build_app_data.py`가 DB에도 upsert하도록

**Files:**
- Modify: `build_app_data.py`
- Test: `tests/test_build_app_data.py`

**Interfaces:**
- Consumes: `init_db` 없음 직접 의존 안 함(스키마는 이미 있다고 가정 — Task 2에서 생성됨)
- Produces: `upsert_products(conn, data: list[dict]) -> None` 함수. `data`는 기존 `to_app_data()`가 만드는 것과 같은 shape(각 항목에 `tacaItemId`, `shareLink`, `name`, `price`, `discountRate`, `imageUrl`, `category`, `reviewCount`, 선택적 `isAllTimeLow`, `dealEndsAt` 키)

- [ ] **Step 1: 실패하는 테스트 먼저 작성**

`tests/test_build_app_data.py` 끝에 추가(기존 `_entry` 헬퍼와 별개로, 이건 쉐어링크 API 원본 shape인 `tacaItemId` 키를 쓰는 진짜 `app_data` 엔트리 shape를 쓴다):

```python
import os

import psycopg2
import pytest

from build_app_data import upsert_products


def _live_db_conn():
    if not os.environ.get("PRODUCTS_DB_DATABASE_URL"):
        return None
    from sharelink_api import _load_dotenv

    _load_dotenv()
    return psycopg2.connect(os.environ["PRODUCTS_DB_DATABASE_URL"])


@pytest.fixture
def conn():
    connection = _live_db_conn()
    if connection is None:
        pytest.skip("PRODUCTS_DB_DATABASE_URL not set - skipping live DB test")
    yield connection
    with connection.cursor() as cur:
        cur.execute("delete from products where source = 'test'")
    connection.commit()
    connection.close()


def test_upsert_products_inserts_then_updates_on_conflict(conn):
    entry = {
        "tacaItemId": 999999,
        "shareLink": "https://toss.im/_m/test-upsert",
        "name": "테스트 상품",
        "price": 1000,
        "discountRate": 60,
        "imageUrl": "https://example.com/a.png",
        "category": "식품",
        "reviewCount": 5,
    }

    upsert_products(conn, [entry], source="test")

    with conn.cursor() as cur:
        cur.execute(
            "select name, price, review_count from products where source = 'test' and source_item_id = %s",
            (str(entry["tacaItemId"]),),
        )
        row = cur.fetchone()
    assert row == ("테스트 상품", 1000, 5)

    updated = {**entry, "price": 900, "reviewCount": 10}
    upsert_products(conn, [updated], source="test")

    with conn.cursor() as cur:
        cur.execute(
            "select count(*), price, review_count from products where source = 'test' and source_item_id = %s"
            " group by price, review_count",
            (str(entry["tacaItemId"]),),
        )
        count, price, review_count = cur.fetchone()
    assert (count, price, review_count) == (1, 900, 10)  # 새 행이 아니라 덮어써짐


def test_upsert_products_maps_optional_fields(conn):
    entry = {
        "tacaItemId": 999998,
        "shareLink": "https://toss.im/_m/test-optional",
        "name": "최저가 테스트",
        "price": 500,
        "discountRate": 90,
        "imageUrl": "https://example.com/b.png",
        "category": "뷰티",
        "reviewCount": 1,
        "isAllTimeLow": True,
        "dealEndsAt": "2026-12-31T23:59:59+09:00",
    }

    upsert_products(conn, [entry], source="test")

    with conn.cursor() as cur:
        cur.execute(
            "select is_all_time_low, deal_ends_at is not null from products"
            " where source = 'test' and source_item_id = %s",
            (str(entry["tacaItemId"]),),
        )
        row = cur.fetchone()
    assert row == (True, True)
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `python3 -m pytest tests/test_build_app_data.py -k upsert -v`
Expected: `FAIL` — `ImportError: cannot import name 'upsert_products'`

- [ ] **Step 3: `build_app_data.py`에 `upsert_products` 구현**

`build_app_data.py` 상단 import에 추가:

```python
import psycopg2
from psycopg2.extras import execute_values
```

`APP_DATA_PATH` 근처(모듈 레벨)에 추가:

```python
DEFAULT_SOURCE = "sharelink"
```

`to_app_data` 함수 뒤, `merge_with_previous` 앞에 추가:

```python
def upsert_products(conn, data: list, source: str = DEFAULT_SOURCE) -> None:
    """app_data 엔트리 리스트를 products 테이블에 upsert한다. (source,
    source_item_id) 충돌 시 UPDATE - 매일 실행되는 배치라 이게 정상 경로다."""
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
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `python3 -m pytest tests/test_build_app_data.py -k upsert -v`
Expected: 두 테스트 모두 `PASSED`

- [ ] **Step 5: `main()`에서 DB에도 쓰도록 연결(파일 쓰기는 유지 — 병행)**

`build_app_data.py`의 `main()`에서 아래 부분:

```python
    home_data = build_home_subset(data)
    HOME_DATA_PATH.write_text(
        json.dumps(home_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"완료: {APP_DATA_PATH} ({len(data)}개 상품), {HOME_DATA_PATH} ({len(home_data)}개 상품)")
```

를 아래로 교체:

```python
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
```

- [ ] **Step 6: 전체 파이프라인 실행해서 DB에 실제 데이터 들어가는지 확인**

Run: `python3 build_app_data.py`
Expected: `완료: ... DB upsert (N개)` 출력 (API 요청 한도 걸려도 그때까지 모은 만큼은 upsert됨)

Run:
```bash
python3 -c "
import os
from sharelink_api import _load_dotenv
_load_dotenv()
import psycopg2
conn = psycopg2.connect(os.environ['PRODUCTS_DB_DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"select count(*) from products where source = 'sharelink'\")
print('상품 수:', cur.fetchone()[0])
"
```
Expected: `app-data/products.json`의 항목 수와 비슷한 숫자(수천 개)

- [ ] **Step 7: Commit**

```bash
git add build_app_data.py tests/test_build_app_data.py
git commit -m "Upsert products into Postgres alongside the existing JSON files"
```

---

### Task 4: 쿼리 헬퍼 (`api/webhook.py`) — DB 접속 + 정렬/커서 SQL 빌더

**Files:**
- Modify: `api/webhook.py`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Produces:
  - `SORT_COLUMNS: dict[str, tuple[str, str]]` — `{"recommend": ("review_count", "desc"), "discount": ("discount_rate", "desc"), "price": ("price", "asc")}`
  - `build_products_query(category: str | None, search: str | None, sort: str, cursor: str | None, limit: int) -> tuple[str, list]` — SQL 문자열과 파라미터 리스트를 반환하는 순수 함수(DB 접속 없이 단위 테스트 가능)
  - `encode_cursor(row: dict) -> str` / `decode_cursor(cursor: str) -> tuple` — base64(json) 왕복

- [ ] **Step 1: 실패하는 테스트 먼저 작성**

`tests/test_webhook.py`에 추가:

```python
from webhook import build_products_query, decode_cursor, encode_cursor


def test_encode_decode_cursor_roundtrip():
    row = {"sort_value": 42, "source": "sharelink", "source_item_id": "abc"}
    cursor = encode_cursor(row)
    assert decode_cursor(cursor) == (42, "sharelink", "abc")


def test_build_products_query_by_category_first_page():
    sql, params = build_products_query(
        category="식품", search=None, sort="recommend", cursor=None, limit=20
    )
    assert "category = %s" in sql
    assert "order by review_count desc" in sql
    assert params == ["식품", 20]


def test_build_products_query_by_category_with_cursor():
    cursor = encode_cursor({"sort_value": 100, "source": "sharelink", "source_item_id": "x"})
    sql, params = build_products_query(
        category="식품", search=None, sort="recommend", cursor=cursor, limit=20
    )
    assert "review_count, source, source_item_id) < (%s, %s, %s)" in sql
    assert params == ["식품", 100, "sharelink", "x", 20]


def test_build_products_query_by_search_uses_ilike():
    sql, params = build_products_query(
        category=None, search="세탁", sort="price", cursor=None, limit=20
    )
    assert "name ilike %s" in sql
    assert "order by price asc" in sql
    assert params == ["%세탁%", 20]


def test_build_products_query_price_sort_cursor_uses_greater_than():
    cursor = encode_cursor({"sort_value": 5000, "source": "sharelink", "source_item_id": "y"})
    sql, params = build_products_query(
        category=None, search="세탁", sort="price", cursor=cursor, limit=20
    )
    assert "price, source, source_item_id) > (%s, %s, %s)" in sql
    assert params == ["%세탁%", 5000, "sharelink", "y", 20]


def test_build_products_query_rejects_unknown_sort():
    import pytest

    with pytest.raises(ValueError):
        build_products_query(category="식품", search=None, sort="bogus", cursor=None, limit=20)
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `python3 -m pytest tests/test_webhook.py -k build_products_query -v`
Expected: `FAIL` — `ImportError: cannot import name 'build_products_query'`

- [ ] **Step 3: `api/webhook.py`에 구현 추가**

파일 상단 import에 추가:

```python
import base64
```
(이미 `import base64`가 있음 - 중복 추가하지 않는다. 없는 것만 추가: `import psycopg2`)

`PRODUCTS_HOME_JSON_PATH` 정의 아래에 추가:

```python
PRODUCTS_DB_URL_ENV = "PRODUCTS_DB_DATABASE_URL"

# 클라이언트(App.tsx)의 기존 SORT_OPTIONS와 동일한 3종만 지원.
# (컬럼명, 방향) - 방향은 정렬 컬럼과 커서 타이브레이커 컬럼 모두에 동일하게 적용된다.
SORT_COLUMNS = {
    "recommend": ("review_count", "desc"),
    "discount": ("discount_rate", "desc"),
    "price": ("price", "asc"),
}


def encode_cursor(row: dict) -> str:
    payload = json.dumps([row["sort_value"], row["source"], row["source_item_id"]])
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple:
    payload = base64.urlsafe_b64decode(cursor.encode()).decode()
    sort_value, source, source_item_id = json.loads(payload)
    return sort_value, source, source_item_id


def build_products_query(
    category: str | None, search: str | None, sort: str, cursor: str | None, limit: int
) -> tuple:
    """category XOR search 중 하나로 필터링해서 (SQL, params)를 만든다.
    OFFSET 없이 keyset 방식 - 정렬 컬럼과 타이브레이커(source,
    source_item_id)를 같은 방향으로 묶어서 튜플 비교한다."""
    if sort not in SORT_COLUMNS:
        raise ValueError(f"unknown sort: {sort}")
    column, direction = SORT_COLUMNS[sort]
    comparator = "<" if direction == "desc" else ">"

    where_clauses = []
    params: list = []
    if category is not None:
        where_clauses.append("category = %s")
        params.append(category)
    if search is not None:
        where_clauses.append("name ilike %s")
        params.append(f"%{search}%")

    if cursor is not None:
        sort_value, cur_source, cur_source_item_id = decode_cursor(cursor)
        where_clauses.append(
            f"({column}, source, source_item_id) {comparator} (%s, %s, %s)"
        )
        params.extend([sort_value, cur_source, cur_source_item_id])

    where_sql = " and ".join(where_clauses)
    sql = (
        f"select * from products where {where_sql} "
        f"order by {column} {direction}, source {direction}, source_item_id {direction} "
        f"limit %s"
    )
    params.append(limit)
    return sql, params
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `python3 -m pytest tests/test_webhook.py -k "cursor or build_products_query" -v`
Expected: 6개 테스트 모두 `PASSED`

- [ ] **Step 5: 전체 webhook 테스트 스위트가 여전히 통과하는지 확인**

Run: `python3 -m pytest tests/test_webhook.py -v`
Expected: 기존 테스트 포함 전부 `PASSED` (이 단계에서 라우팅은 아직 안 건드렸으므로 기존 동작 무변화)

- [ ] **Step 6: Commit**

```bash
git add api/webhook.py tests/test_webhook.py
git commit -m "Add keyset-pagination query builder for the products API"
```

---

### Task 5: `/api/products/home`을 DB 쿼리로 전환 + `/api/products?category=`/`?search=` 라우트 추가

**Files:**
- Modify: `api/webhook.py`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: Task 4의 `build_products_query`, `encode_cursor`, `SORT_COLUMNS`
- Produces: `fetch_home_products(conn) -> list[dict]`, `fetch_products_page(conn, category, search, sort, cursor, limit) -> dict`(`{"items": [...], "nextCursor": str | None}`)

- [ ] **Step 1: 실패하는 테스트 먼저 작성(라우팅 로직, DB는 fake cursor로 대체)**

`tests/test_webhook.py`에 추가:

```python
from webhook import fetch_products_page


class _FakeCursor:
    def __init__(self, rows, columns):
        self._rows = rows
        self.description = [(c,) for c in columns]

    def execute(self, sql, params):
        self.executed = (sql, params)

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _FakeConn:
    def __init__(self, rows, columns):
        self._cursor = _FakeCursor(rows, columns)

    def cursor(self):
        return self._cursor


def test_fetch_products_page_maps_rows_to_dicts_and_builds_next_cursor():
    columns = [
        "source", "source_item_id", "share_link", "name", "price",
        "discount_rate", "image_url", "category", "review_count",
        "is_all_time_low", "deal_ends_at", "updated_at",
    ]
    row = (
        "sharelink", "123", "https://toss.im/x", "상품", 1000, 60,
        "https://img", "식품", 7, False, None, None,
    )
    conn = _FakeConn(rows=[row], columns=columns)

    result = fetch_products_page(
        conn, category="식품", search=None, sort="recommend", cursor=None, limit=1
    )

    assert result["items"] == [{
        "tacaItemId": "123",
        "shareLink": "https://toss.im/x",
        "name": "상품",
        "price": 1000,
        "discountRate": 60,
        "imageUrl": "https://img",
        "category": "식품",
        "reviewCount": 7,
        "isAllTimeLow": False,
    }]
    assert result["nextCursor"] is not None  # limit(1)만큼 꽉 찼으니 다음 페이지 있음


def test_fetch_products_page_no_next_cursor_when_fewer_than_limit():
    columns = [
        "source", "source_item_id", "share_link", "name", "price",
        "discount_rate", "image_url", "category", "review_count",
        "is_all_time_low", "deal_ends_at", "updated_at",
    ]
    conn = _FakeConn(rows=[], columns=columns)

    result = fetch_products_page(
        conn, category="식품", search=None, sort="recommend", cursor=None, limit=20
    )

    assert result["items"] == []
    assert result["nextCursor"] is None
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `python3 -m pytest tests/test_webhook.py -k fetch_products_page -v`
Expected: `FAIL` — `ImportError: cannot import name 'fetch_products_page'`

- [ ] **Step 3: `fetch_products_page` + `fetch_home_products` 구현**

`api/webhook.py`의 `build_products_query` 함수 뒤에 추가:

```python
def _row_to_product(row: tuple, columns: list) -> dict:
    record = dict(zip(columns, row))
    product = {
        "tacaItemId": record["source_item_id"],
        "shareLink": record["share_link"],
        "name": record["name"],
        "price": record["price"],
        "discountRate": record["discount_rate"],
        "imageUrl": record["image_url"],
        "category": record["category"],
        "reviewCount": record["review_count"],
        "isAllTimeLow": record["is_all_time_low"],
    }
    if record["deal_ends_at"] is not None:
        product["dealEndsAt"] = record["deal_ends_at"].isoformat()
    return product


def fetch_products_page(
    conn, category: str | None, search: str | None, sort: str, cursor: str | None, limit: int
) -> dict:
    sql, params = build_products_query(category, search, sort, cursor, limit)
    column, _direction = SORT_COLUMNS[sort]
    with conn.cursor() as cur:
        cur.execute(sql, params)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    items = [_row_to_product(row, columns) for row in rows]

    next_cursor = None
    if len(rows) == limit:
        last = dict(zip(columns, rows[-1]))
        next_cursor = encode_cursor({
            "sort_value": last[column],
            "source": last["source"],
            "source_item_id": last["source_item_id"],
        })

    return {"items": items, "nextCursor": next_cursor}


def fetch_home_products(conn) -> list:
    """카테고리별 상위 20 + 역대최저가 상위 20 + 캐러셀 후보(할인 80%+) 상위
    20을 합쳐 review_count 순으로 반환한다 - build_home_subset()의 SQL 버전."""
    sql = """
        with category_top as (
            select *, row_number() over (partition by category order by review_count desc) as rn
            from products
        ),
        all_time_low_top as (
            select *, row_number() over (order by review_count desc) as rn
            from products where is_all_time_low
        ),
        carousel_top as (
            select *, row_number() over (order by review_count desc) as rn
            from products where discount_rate >= 80
        )
        select distinct on (share_link) *
        from (
            select * from category_top where rn <= 20
            union all
            select * from all_time_low_top where rn <= 20
            union all
            select * from carousel_top where rn <= 20
        ) combined
        order by share_link, review_count desc
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return [_row_to_product(row, columns) for row in rows]
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `python3 -m pytest tests/test_webhook.py -k fetch_products_page -v`
Expected: 두 테스트 모두 `PASSED`

- [ ] **Step 5: 라우팅 연결 — `do_GET`과 `_handle_products_request` 교체**

기존:

```python
    def do_GET(self):
        if self.path.startswith("/api/products/home"):
            self._handle_products_request(PRODUCTS_HOME_JSON_PATH)
        elif self.path.startswith("/api/products"):
            self._handle_products_request(PRODUCTS_JSON_PATH)
        else:
            self.send_response(404)
            self.end_headers()
```

아래로 교체 — `/api/products`에 쿼리 파라미터가 붙으면 새 페이지네이션
핸들러로, 파라미터 없이 순수 `/api/products`면 기존 전체 덤프 핸들러로
간다(기존 App.tsx가 파라미터 없이 호출하니 무변화):

```python
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/products/home":
            self._handle_home_products_request()
        elif path == "/api/products":
            query = urllib.parse.urlparse(self.path).query
            if urllib.parse.parse_qs(query):
                self._handle_products_page_request()
            else:
                self._handle_products_request(PRODUCTS_JSON_PATH)
        else:
            self.send_response(404)
            self.end_headers()
```

새 핸들러 두 개를 기존 `_handle_products_request` 메서드 뒤에 추가:

```python
    def _handle_home_products_request(self):
        db_url = os.environ.get(PRODUCTS_DB_URL_ENV)
        if not db_url:
            self._respond(500, {"error": "PRODUCTS_DB_DATABASE_URL not configured"}, cors=True)
            return
        conn = psycopg2.connect(db_url)
        try:
            items = fetch_home_products(conn)
        finally:
            conn.close()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(items).encode())

    def _handle_products_page_request(self):
        db_url = os.environ.get(PRODUCTS_DB_URL_ENV)
        if not db_url:
            self._respond(500, {"error": "PRODUCTS_DB_DATABASE_URL not configured"}, cors=True)
            return

        query = urllib.parse.urlparse(self.path).query
        parsed = urllib.parse.parse_qs(query)
        category = parsed.get("category", [None])[0]
        search = parsed.get("search", [None])[0]
        sort = parsed.get("sort", ["recommend"])[0]
        cursor = parsed.get("cursor", [None])[0]
        limit = int(parsed.get("limit", ["20"])[0])

        if not category and not search:
            self._respond(400, {"error": "category or search is required"}, cors=True)
            return
        if category and search:
            self._respond(400, {"error": "category and search are mutually exclusive"}, cors=True)
            return

        conn = psycopg2.connect(db_url)
        try:
            result = fetch_products_page(conn, category, search, sort, cursor, limit)
        except ValueError as e:
            self._respond(400, {"error": str(e)}, cors=True)
            return
        finally:
            conn.close()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"items": result["items"], "nextCursor": result["nextCursor"]}).encode())
```

- [ ] **Step 6: 기존 테스트 전부 다시 통과하는지 확인**

Run: `python3 -m pytest tests/test_webhook.py -v`
Expected: 전부 `PASSED`

- [ ] **Step 7: Commit**

```bash
git add api/webhook.py tests/test_webhook.py
git commit -m "Serve home/category/search from Postgres via new query endpoints"
```

---

### Task 6: 배포 후 실제 엔드포인트 확인 (수동 검증)

**Files:** 없음 (검증만)

- [ ] **Step 1: 푸시해서 Vercel 배포 반영**

Run: `git push`

- [ ] **Step 2: 배포 반영 대기 후 홈 엔드포인트 확인**

Run: `sleep 20 && curl -sS --compressed https://shaerlink.vercel.app/api/products/home | python3 -c "import json,sys; d=json.load(sys.stdin); print('items:', len(d)); print(d[0])"`
Expected: 에러 없이 상품 리스트 출력, 각 항목이 `tacaItemId`/`name`/`price`/`discountRate`/`imageUrl`/`category`/`reviewCount`/`shareLink` 키를 가짐 (기존 파일 기반 응답과 동일한 shape)

- [ ] **Step 3: 카테고리 페이지네이션 확인**

Run: `curl -sS --compressed "https://shaerlink.vercel.app/api/products?category=식품&limit=5" | python3 -m json.tool`
Expected: `{"items": [...5개...], "nextCursor": "..."}` 형태. 그 `nextCursor` 값을 복사해서:

Run: `curl -sS --compressed "https://shaerlink.vercel.app/api/products?category=식품&limit=5&cursor=<위에서 받은 값>" | python3 -m json.tool`
Expected: 다른 5개 항목(이전 페이지와 안 겹침)

- [ ] **Step 4: 검색 확인**

Run: `curl -sS --compressed "https://shaerlink.vercel.app/api/products?search=세탁&limit=5" | python3 -m json.tool`
Expected: 이름에 "세탁"이 포함된 상품들 반환

- [ ] **Step 5: 기존 전체 덤프 엔드포인트가 여전히 무변화인지 확인**

Run: `curl -sS --compressed -o /dev/null -w "%{http_code}\n" https://shaerlink.vercel.app/api/products`
Expected: `200` (파라미터 없는 호출은 기존 파일 기반 핸들러로 그대로 감)

- [ ] **Step 6: 잘못된 요청 처리 확인**

Run: `curl -sS -w "\n%{http_code}\n" "https://shaerlink.vercel.app/api/products?category=식품&search=세탁"`
Expected: `400`과 에러 메시지 (category/search 동시 사용 거부)

Run: `curl -sS -w "\n%{http_code}\n" "https://shaerlink.vercel.app/api/products?sort=bogus&category=식품"`
Expected: `400`과 `unknown sort: bogus`
