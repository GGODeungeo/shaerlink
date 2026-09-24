# 상품 카탈로그 DB 전환 — 2단계 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `App.tsx`가 전체 카탈로그를 한 번에 들고 있지 않고, 화면별로 필요한
만큼만 DB 기반 API에서 가져오도록 리팩터링하고, 이제 쓸모없어진 구
전체덤프 엔드포인트와 죽은 파일을 정리한다.

**Architecture:** 홈 API(`/api/products/home`)에 전역 리뷰순 top-30 풀을
추가해 랭킹/이벤트 화면이 프론트 코드 변경 없이 계속 동작하게 하고, 새
배치 조회 API(`/api/products/batch?ids=`)로 찜/최근본이 임의의 상품을
`shareLink`로 다시 가져온다. `App.tsx`는 화면별로 상태를 분리하고,
카테고리/검색처럼 모양이 같은 두 화면은 공용 훅(`usePaginatedProducts`)
하나로 처리한다. 구 `/api/products`(전체 덤프) 라우트와 죽은
`products-home.json` 산출물을 제거한다.

**Tech Stack:** Python 3.12, psycopg2-binary, Postgres(Neon), pytest,
React 19, TypeScript

**Spec:** `docs/superpowers/specs/2026-09-24-product-catalog-db-migration-phase2-design.md`

## Global Constraints

- `App.tsx`가 보여주는 실제 동작(정렬 옵션, "더보기" 페이지네이션, 검색
  결과, 랭킹/이벤트 내용)은 사용자 입장에서 기존과 동일하게 유지한다
- `app-data/products.json` 파일 쓰기는 그대로 유지한다 —
  `.github/workflows/refresh-data.yml`이 이 파일 개수를 CI 안전장치로 씀
- 프론트엔드에는 React 테스트 프레임워크가 없음(확인됨) — 프론트 작업의
  검증은 `npx tsc -b`(타입체크) + 배포 후 curl/브라우저 수동 확인으로 한다
- 별도 브랜치 없이 `main`에 직접, 작업 단위로 커밋한다

---

### Task 1: 홈 API에 전역 리뷰순 top-30 풀 추가

**Files:**
- Modify: `api/webhook.py:254-284` (`fetch_home_products`)
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: 없음 (기존 `fetch_home_products(conn) -> list` 시그니처 그대로)
- Produces: `fetch_home_products`의 반환값에 카테고리 무관 전역 리뷰순
  top-30이 포함됨을 보장 (Task 7에서 프론트가 이 보장에 의존)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_webhook.py` 상단 import 블록에 `fetch_home_products`를
추가하고(기존 `from webhook import (...)` 블록의 알파벳 순서 위치에 삽입),
`os`, `psycopg2`, `pytest`를 새로 import하고, `_load_dotenv`를 module
level에서 호출한다(지연 로딩 전에 skipif가 env를 읽는 버그를 피하기 위한
기존 프로젝트 관례 — `tests/test_build_app_data.py`와 동일 패턴):

```python
import os

import psycopg2
import pytest

from sharelink_api import _load_dotenv

_load_dotenv()  # module level - skipif가 실제 env를 봐야 한다 (지연 로딩 전에 읽으면 오탐)
```

`from webhook import (...)` 블록에 `fetch_home_products`를 추가:

```python
from webhook import (
    _verify_signature,
    _within_clock_skew,
    build_products_query,
    decode_cursor,
    encode_cursor,
    fetch_home_products,
    fetch_products_page,
    grant_click_reward,
    grant_reward,
    is_reward_eligible,
    issue_tracked_link,
)
```

파일 맨 아래에 `db_conn` 픽스처와 테스트를 추가:

```python
@pytest.fixture
def db_conn():
    if not os.environ.get("PRODUCTS_DB_DATABASE_URL"):
        pytest.skip("PRODUCTS_DB_DATABASE_URL not set - skipping live DB test")
    connection = psycopg2.connect(os.environ["PRODUCTS_DB_DATABASE_URL"])
    yield connection
    with connection.cursor() as cur:
        cur.execute("delete from products where source = 'test'")
    connection.commit()
    connection.close()


def test_fetch_home_products_includes_global_top_review_items_even_when_category_cutoff_excludes_them(db_conn):
    # 21개를 전부 같은 카테고리에 넣어서 카테고리별 top-20 컷오프(rn<=20)가
    # 21번째 항목을 잘라내게 만든다. review_count를 실제 운영 데이터보다
    # 훨씬 크게 잡아서(9999999대) 이 21개가 항상 전역 상위 30위 안에 들도록
    # 보장한다 - 실 운영 테이블에 어떤 데이터가 있든 이 테스트 결과가
    # 흔들리지 않는다.
    base_review_count = 9_999_999
    with db_conn.cursor() as cur:
        for i in range(21):
            cur.execute(
                """
                insert into products (
                    source, source_item_id, share_link, name, price,
                    discount_rate, image_url, category, review_count, updated_at
                ) values ('test', %s, %s, %s, 1000, 60, 'https://example.com/x.png', 'test-category', %s, now())
                """,
                (f"batch-{i}", f"https://test.example/item-{i}", f"테스트 상품 {i}", base_review_count - i),
            )
    db_conn.commit()

    items = fetch_home_products(db_conn)

    share_links = {p["shareLink"] for p in items}
    assert "https://test.example/item-20" in share_links  # 카테고리 내 21번째(최저) - 카테고리 top-20에서는 잘림
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python3 -m pytest tests/test_webhook.py::test_fetch_home_products_includes_global_top_review_items_even_when_category_cutoff_excludes_them -v`
Expected: FAIL (`https://test.example/item-20`가 `share_links`에 없음 —
아직 전역 풀이 없어서 카테고리 top-20 컷오프에 걸려 빠짐)

- [ ] **Step 3: `fetch_home_products`에 전역 top-30 풀 추가**

`api/webhook.py`의 `fetch_home_products` 함수 전체를 아래로 교체:

```python
def fetch_home_products(conn) -> list:
    """카테고리별 상위 20 + 역대최저가 상위 20 + 캐러셀 후보(할인 80%+) 상위
    20 + 전역 리뷰순 상위 30(카테고리 무관 - PopularRanking/TodaysPickEvent가
    이 배열에서 직접 정렬·slice하므로 여기 없으면 두 화면에서 빠질 수 있음)을
    합쳐 review_count 순으로 반환한다."""
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
        ),
        global_top as (
            select *, row_number() over (order by review_count desc) as rn
            from products
        )
        select distinct on (share_link) *
        from (
            select * from category_top where rn <= 20
            union all
            select * from all_time_low_top where rn <= 20
            union all
            select * from carousel_top where rn <= 20
            union all
            select * from global_top where rn <= 30
        ) combined
        order by share_link, review_count desc
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return [_row_to_product(row, columns) for row in rows]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_webhook.py -v`
Expected: 전부 PASS (기존 테스트 포함)

- [ ] **Step 5: 커밋**

```bash
git add api/webhook.py tests/test_webhook.py
git commit -m "Add global top-30 review-count pool to home API for ranking/event views"
```

---

### Task 2: 배치 조회 API 신설 (`/api/products/batch?ids=`)

**Files:**
- Modify: `api/webhook.py`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: `_row_to_product(row, columns) -> dict` (기존)
- Produces: `fetch_products_by_ids(conn, share_links: list) -> list`,
  `GET /api/products/batch?ids=<shareLink1>,<shareLink2>,...` →
  `{"items": [...]}` (Task 7에서 프론트 찜/최근본이 사용)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_webhook.py`의 import 블록에 `fetch_products_by_ids` 추가:

```python
from webhook import (
    _verify_signature,
    _within_clock_skew,
    build_products_query,
    decode_cursor,
    encode_cursor,
    fetch_home_products,
    fetch_products_by_ids,
    fetch_products_page,
    grant_click_reward,
    grant_reward,
    is_reward_eligible,
    issue_tracked_link,
)
```

`_FakeConn`/`_FakeCursor` 정의 아래(파일 하단, Task 1에서 추가한 `db_conn`
픽스처 앞)에 테스트 추가:

```python
def test_fetch_products_by_ids_maps_rows_to_dicts():
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

    result = fetch_products_by_ids(conn, ["https://toss.im/x"])

    assert result == [{
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


def test_fetch_products_by_ids_returns_empty_list_without_querying_when_no_ids():
    result = fetch_products_by_ids(None, [])  # conn=None이어도 에러 없어야 함 - 쿼리 자체를 안 함
    assert result == []
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python3 -m pytest tests/test_webhook.py::test_fetch_products_by_ids_maps_rows_to_dicts -v`
Expected: FAIL (`ImportError: cannot import name 'fetch_products_by_ids'`)

- [ ] **Step 3: `fetch_products_by_ids` + 핸들러 + 라우트 추가**

`api/webhook.py`의 `fetch_home_products` 함수 바로 뒤(Task 1에서 수정한
함수 다음)에 추가:

```python
def fetch_products_by_ids(conn, share_links: list) -> list:
    """찜/최근본처럼 임의의 shareLink 목록으로 정확히 그 상품들만 조회한다.
    순서는 보장하지 않음 - 호출 측(App.tsx)이 로컬에 저장된 순서대로
    재배열한다. 존재하지 않는 shareLink는 결과에서 조용히 빠진다."""
    if not share_links:
        return []
    with conn.cursor() as cur:
        cur.execute("select * from products where share_link = any(%s)", (share_links,))
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return [_row_to_product(row, columns) for row in rows]
```

`class handler`의 `do_GET`에 `/api/products/batch` 분기를 추가(전체 교체):

```python
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/products/home":
            self._handle_home_products_request()
        elif path == "/api/products/batch":
            self._handle_products_batch_request()
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

`_handle_home_products_request` 메서드 바로 뒤에 새 핸들러 추가:

```python
    def _handle_products_batch_request(self):
        db_url = os.environ.get(PRODUCTS_DB_URL_ENV)
        if not db_url:
            self._respond(500, {"error": "PRODUCTS_DB_DATABASE_URL not configured"}, cors=True)
            return

        query = urllib.parse.urlparse(self.path).query
        parsed = urllib.parse.parse_qs(query)
        ids_param = parsed.get("ids", [""])[0]
        share_links = [s for s in ids_param.split(",") if s]
        if not share_links:
            self._respond(400, {"error": "ids is required"}, cors=True)
            return

        conn = psycopg2.connect(db_url)
        try:
            items = fetch_products_by_ids(conn, share_links)
        finally:
            conn.close()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"items": items}).encode())
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_webhook.py -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add api/webhook.py tests/test_webhook.py
git commit -m "Add /api/products/batch?ids= endpoint for favorites/recently-viewed lookups"
```

---

### Task 3: 구 전체덤프 라우트/상수 제거

**Files:**
- Modify: `api/webhook.py`

**Interfaces:**
- Consumes: 없음
- Produces: `/api/products`는 이제 항상 `_handle_products_page_request()`로
  라우팅됨(파라미터 없으면 그 안에서 `400 {"error": "category or search is
  required"}` 반환)

- [ ] **Step 1: `do_GET` 단순화**

`api/webhook.py`의 `do_GET`을 아래로 교체(Task 2에서 추가한 batch 분기는
유지):

```python
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/products/home":
            self._handle_home_products_request()
        elif path == "/api/products/batch":
            self._handle_products_batch_request()
        elif path == "/api/products":
            self._handle_products_page_request()
        else:
            self.send_response(404)
            self.end_headers()
```

- [ ] **Step 2: `_handle_products_request` 메서드 삭제**

`api/webhook.py`에서 아래 메서드 전체를 삭제:

```python
    def _handle_products_request(self, path: Path):
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            self._respond(404, {"error": f"{path.name} not found"}, cors=True)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)
```

- [ ] **Step 3: 죽은 상수/import 삭제**

`api/webhook.py` 상단에서 아래 두 줄을 삭제:

```python
PRODUCTS_JSON_PATH = Path(__file__).resolve().parent.parent / "app-data" / "products.json"
PRODUCTS_HOME_JSON_PATH = Path(__file__).resolve().parent.parent / "app-data" / "products-home.json"
```

`from pathlib import Path` import도 삭제(이 두 상수 말고 `Path`를 쓰는 곳이
없음 — 삭제 후 `grep -n "Path" api/webhook.py`로 재확인).

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_webhook.py -v`
Expected: 전부 PASS

Run: `grep -n "Path" api/webhook.py`
Expected: 아무 결과 없음(빈 출력)

- [ ] **Step 5: 커밋**

```bash
git add api/webhook.py
git commit -m "Remove old full-dump /api/products route and dead file-path constants"
```

---

### Task 4: 파이프라인 정리 — `build_home_subset`/`products-home.json` 삭제

**Files:**
- Modify: `build_app_data.py`
- Modify: `tests/test_build_app_data.py`

**Interfaces:**
- Consumes: 없음
- Produces: 없음(순수 삭제 — `build_home_subset`도 그 산출물
  `products-home.json`도 리포 어디에서도 더 이상 안 쓰임, `PRODUCTS_HOME_JSON_PATH`가
  Task 3에서 이미 삭제됨으로써 확인됨)

- [ ] **Step 1: `build_app_data.py`에서 `build_home_subset` 제거**

`HOME_DATA_PATH = Path("app-data/products-home.json")` 줄을 삭제.

`HOME_POOL_SIZE = 20`과 `CAROUSEL_MIN_DISCOUNT = 80` 상수도 함께 삭제 —
둘 다 `build_home_subset`에서만 쓰이던 값이라(확인됨) 그 함수를 지우면
같이 죽는다:

```python
# Mirrors the client's own pool sizes (App.tsx SHELF_POOL_SIZE,
# TopDealsCarousel POOL_SIZE) - the home subset only needs to cover what the
# home screen actually draws from, not the full catalog.
HOME_POOL_SIZE = 20
CAROUSEL_MIN_DISCOUNT = 80
```

`build_home_subset` 함수 전체(아래 블록)를 삭제:

```python
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
```

`main()`에서 아래 블록을 삭제:

```python
    home_data = build_home_subset(data)
    HOME_DATA_PATH.write_text(
        json.dumps(home_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

```

`main()`의 마지막 `if db_url: ... else: ...` 블록을 아래로 교체:

```python
    db_url = os.environ.get("PRODUCTS_DB_DATABASE_URL")
    if db_url:
        connection = psycopg2.connect(db_url)
        try:
            upsert_products(connection, data)
        finally:
            connection.close()
        print(f"완료: {APP_DATA_PATH} ({len(data)}개), DB upsert ({len(data)}개)")
    else:
        print(f"완료: {APP_DATA_PATH} ({len(data)}개 상품) - PRODUCTS_DB_DATABASE_URL 없어서 DB는 건너뜀")
```

- [ ] **Step 2: `tests/test_build_app_data.py`에서 관련 테스트/import/헬퍼 제거**

`from build_app_data import (...)` 블록에서 `build_home_subset`을 제거.

`_entry` 헬퍼 함수 전체(아래)를 삭제 — `build_home_subset` 테스트에서만
쓰이던 헬퍼라 같이 죽음:

```python
def _entry(share_link, category="식품", review_count=0, discount_rate=51, is_all_time_low=False, **overrides):
    # tacaItemId deliberately omitted by default - app_data entries carried
    # forward from before the tacaItemId backfill don't have one, and
    # build_home_subset must not choke on that (unlike merge_unique, which
    # keys on tacaItemId and does require it).
    entry = {
        "shareLink": share_link,
        "category": category,
        "reviewCount": review_count,
        "discountRate": discount_rate,
    }
    if is_all_time_low:
        entry["isAllTimeLow"] = True
    entry.update(overrides)
    return entry
```

아래 4개 테스트 함수를 전부 삭제:
`test_build_home_subset_caps_each_category_to_pool_size`,
`test_build_home_subset_includes_all_time_low_and_carousel_pools`,
`test_build_home_subset_dedupes_by_share_link_not_taca_item_id`,
`test_build_home_subset_ignores_missing_taca_item_id`.

- [ ] **Step 3: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_build_app_data.py -v`
Expected: 전부 PASS (삭제된 4개는 목록에서 사라짐)

Run: `grep -rn "build_home_subset\|HOME_DATA_PATH\|products-home\|HOME_POOL_SIZE\|CAROUSEL_MIN_DISCOUNT" build_app_data.py tests/ api/`
Expected: 아무 결과 없음(빈 출력)

- [ ] **Step 4: 커밋**

```bash
git add build_app_data.py tests/test_build_app_data.py
git commit -m "Remove dead build_home_subset/products-home.json output - home API is DB-driven now"
```

---

### Task 5: `usePaginatedProducts` 공용 훅 작성

**Files:**
- Create: `deep-discount-deals/src/usePaginatedProducts.ts`
- Modify: `deep-discount-deals/src/types.ts`

**Interfaces:**
- Consumes: `Product` 타입(`./types`)
- Produces: `SortKey` 타입(`./types`로 이동),
  `usePaginatedProducts(params: { category?: string; search?: string; sort: SortKey }) => { items: Product[]; status: 'loading' | 'error' | 'ready'; hasMore: boolean; loadMore: () => void }`
  (Task 6에서 `App.tsx`의 카테고리/검색 화면이 사용)

- [ ] **Step 1: `SortKey`를 `types.ts`로 이동**

`deep-discount-deals/src/types.ts` 전체를 아래로 교체:

```ts
export type Product = {
  name: string;
  price: number;
  discountRate: number;
  imageUrl: string;
  category: string;
  shareLink: string;
  reviewCount: number;
  dealEndsAt?: string;
  isAllTimeLow?: boolean;
  tacaItemId?: number;
};

export type SortKey = 'recommend' | 'discount' | 'price';
```

- [ ] **Step 2: `usePaginatedProducts.ts` 작성**

`deep-discount-deals/src/usePaginatedProducts.ts` 새로 생성:

```ts
import { useEffect, useState } from 'react';
import type { Product, SortKey } from './types';

const PRODUCTS_URL = 'https://shaerlink.vercel.app/api/products';
const DEFAULT_LIMIT = 20;

type Status = 'loading' | 'error' | 'ready';

type PageState = {
  items: Product[];
  nextCursor: string | null;
  status: Status;
};

function buildUrl(params: { category?: string; search?: string; sort: SortKey; cursor?: string | null }) {
  const qs = new URLSearchParams({ sort: params.sort, limit: String(DEFAULT_LIMIT) });
  if (params.category) qs.set('category', params.category);
  if (params.search) qs.set('search', params.search);
  if (params.cursor) qs.set('cursor', params.cursor);
  return `${PRODUCTS_URL}?${qs}`;
}

/** category/search 중 하나로 서버에서 커서 페이지네이션된 상품 목록을
 * 가져온다. category/search/sort 중 하나라도 바뀌면 1페이지부터 새로
 * 가져오고, 둘 다 없으면(undefined) fetch하지 않는다 - 카테고리를 아직 안
 * 고른 홈 화면에서 이 훅을 미리 호출해도 조용히 아무 것도 안 한다. */
export function usePaginatedProducts(params: { category?: string; search?: string; sort: SortKey }) {
  const { category, search, sort } = params;
  const [state, setState] = useState<PageState>({ items: [], nextCursor: null, status: 'loading' });

  useEffect(() => {
    if (!category && !search) return;
    setState({ items: [], nextCursor: null, status: 'loading' });
    fetch(buildUrl({ category, search, sort }))
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { items: Product[]; nextCursor: string | null }) =>
        setState({ items: data.items, nextCursor: data.nextCursor, status: 'ready' })
      )
      .catch(() => setState({ items: [], nextCursor: null, status: 'error' }));
  }, [category, search, sort]);

  const loadMore = () => {
    if (!state.nextCursor) return;
    fetch(buildUrl({ category, search, sort, cursor: state.nextCursor }))
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { items: Product[]; nextCursor: string | null }) =>
        setState((prev) => ({
          items: [...prev.items, ...data.items],
          nextCursor: data.nextCursor,
          status: 'ready',
        }))
      )
      .catch(() => {});
  };

  return { items: state.items, status: state.status, hasMore: state.nextCursor !== null, loadMore };
}
```

- [ ] **Step 3: 타입체크로 검증**

Run: `cd deep-discount-deals && npx tsc -b`
Expected: 에러 없이 종료 — `App.tsx`는 아직 Task 6 전이라 `./types`에서
`SortKey`를 import하지 않고 자체 `type SortKey = ...`를 그대로 갖고 있어
이름은 같아도 서로 독립적인 타입이라 충돌 없음

- [ ] **Step 4: 커밋**

```bash
git add deep-discount-deals/src/types.ts deep-discount-deals/src/usePaginatedProducts.ts
git commit -m "Add usePaginatedProducts hook for category/search server-side pagination"
```

---

### Task 6: `App.tsx` 리팩터링 — 화면별 상태 분리

**Files:**
- Modify: `deep-discount-deals/src/App.tsx` (전체 재작성)

**Interfaces:**
- Consumes: `usePaginatedProducts` (Task 5), `/api/products/home`(Task 1로
  전역 top-30 포함), `/api/products/batch?ids=`(Task 2)
- Produces: 없음(최종 소비자 — 화면 컴포넌트)

- [ ] **Step 1: `App.tsx` 전체를 아래로 교체**

`deep-discount-deals/src/App.tsx` 전체 내용을 아래로 교체:

```tsx
import { useEffect, useRef, useState } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import { ProductCard } from './ProductCard';
import { TopDealsCarousel } from './TopDealsCarousel';
import { PurchaseSheet } from './PurchaseSheet';
import { Bag, Heart, Search } from './components/icons';
import { useFavorites } from './useFavorites';
import { useRecentlyViewed } from './useRecentlyViewed';
import { usePaginatedProducts } from './usePaginatedProducts';
import { dedupeByImage } from './dedupeByImage';
import { dailyShuffle } from './dailyShuffle';
import { TodaysPickEvent } from './TodaysPickEvent';
import { PopularRanking } from './PopularRanking';
import { BannerAd } from './BannerAd';
import { PushOptInCard } from './PushOptInCard';
import type { Product, SortKey } from './types';
import './App.css';

const HOME_DATA_URL = 'https://shaerlink.vercel.app/api/products/home';
const PRODUCTS_BATCH_URL = 'https://shaerlink.vercel.app/api/products/batch';

const CATEGORY_EMOJI: Record<string, string> = {
  '식품': '🍎',
  '가구/홈데코': '🛋️',
  '가전/디지털': '📱',
  '뷰티': '💄',
  '생활용품': '🧻',
  '스포츠/레져': '⚽',
  '자동차용품': '🚗',
  '주방용품': '🍳',
  '완구/취미': '🧸',
  '반려/애완용품': '🐾',
  '패션의류잡화': '👕',
  '문구/오피스': '📎',
  '음반/DVD': '💿',
  '출산/유아동': '🍼',
  '도서': '📚',
  '여행/취미': '✈️',
};
const DEFAULT_CATEGORY_EMOJI = '🏷️';
const SHELF_SIZE = 10;
const SHELF_POOL_SIZE = SHELF_SIZE * 2;

function groupByCategory(products: Product[]) {
  const byCategory = new Map<string, Product[]>();
  for (const product of products) {
    const list = byCategory.get(product.category) ?? [];
    list.push(product);
    byCategory.set(product.category, list);
  }
  return [...byCategory.entries()]
    .map(([category, items]) => ({ label: category, products: items }))
    .sort((a, b) => b.products.length - a.products.length);
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'ready'; products: Product[] };

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'recommend', label: '추천순' },
  { key: 'discount', label: '할인율순' },
  { key: 'price', label: '낮은 가격순' },
];

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;

function sortProducts(products: Product[], sort: SortKey) {
  return [...products].sort((a, b) => {
    if (sort === 'discount') return b.discountRate - a.discountRate;
    if (sort === 'price') return a.price - b.price;
    return b.reviewCount - a.reviewCount;
  });
}

function App() {
  const [homeState, setHomeState] = useState<LoadState>({ status: 'loading' });
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>('recommend');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [viewingFavorites, setViewingFavorites] = useState(false);
  const [viewingEvent, setViewingEvent] = useState(false);
  const [viewingRecentlyViewed, setViewingRecentlyViewed] = useState(false);
  const [viewingRanking, setViewingRanking] = useState(false);
  const [favoriteItems, setFavoriteItems] = useState<Product[]>([]);
  const [recentItems, setRecentItems] = useState<Product[]>([]);
  const { favorites, toggleFavorite } = useFavorites();
  const { recentIds, recordView, removeView, clearAll } = useRecentlyViewed();

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  const isSearching = debouncedSearch.length > 0;
  const categoryState = usePaginatedProducts({ category: selectedCategory ?? undefined, sort });
  const searchState = usePaginatedProducts({ search: isSearching ? debouncedSearch : undefined, sort });

  const handleSelectProduct = (product: Product) => {
    recordView(product.shareLink);
    setSelectedProduct(product);
  };

  const selectCategory = (label: string) => {
    setSelectedCategory(label);
    setViewingFavorites(false);
    setViewingEvent(false);
    setViewingRecentlyViewed(false);
    setViewingRanking(false);
    setVisibleCount(PAGE_SIZE);
  };

  const openFavorites = () => {
    Analytics.click({ log_name: 'favorites_nav_click', favorite_count: favorites.size });
    setViewingFavorites(true);
    setViewingEvent(false);
    setViewingRecentlyViewed(false);
    setViewingRanking(false);
    setVisibleCount(PAGE_SIZE);
  };

  const openEvent = () => {
    setViewingEvent(true);
    setViewingFavorites(false);
    setViewingRecentlyViewed(false);
    setViewingRanking(false);
  };

  const openRecentlyViewedPage = () => {
    Analytics.click({ log_name: 'recently_viewed_nav_click', item_count: recentIds.length });
    setViewingRecentlyViewed(true);
    setViewingFavorites(false);
    setViewingEvent(false);
    setViewingRanking(false);
    setVisibleCount(PAGE_SIZE);
  };

  const openHome = () => {
    if (isSubView) window.history.back();
  };

  const openRanking = () => {
    Analytics.click({ log_name: 'ranking_teaser_click' });
    setViewingRanking(true);
    setViewingFavorites(false);
    setViewingEvent(false);
    setViewingRecentlyViewed(false);
    setVisibleCount(PAGE_SIZE);
  };

  const fetchJson = (url: string): Promise<Product[]> =>
    fetch(url).then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    });

  const fetchHomeProducts = () => {
    fetchJson(HOME_DATA_URL)
      .then((products) => setHomeState({ status: 'ready', products }))
      .catch(() => setHomeState({ status: 'error' }));
  };

  useEffect(fetchHomeProducts, []);

  // 찜 화면에 들어갈 때 스냅샷을 한 번만 가져온다. 화면 안에서 찜 해제는
  // favorites Set 변화를 렌더 시점에 바로 필터링해 즉시 반영하고, 여기서
  // 다시 fetch하지 않는다 - 안 그러면 매 토글마다 네트워크 왕복이 생겨
  // 카드가 사라지는 게 한 박자 늦게 보인다. (이 화면 안에서는 찜 추가가
  // 불가능하므로 - 항상 isFavorite=true로 렌더 - 스냅샷 이후의 축소만
  // 반영하면 충분하다.)
  useEffect(() => {
    if (!viewingFavorites) return;
    const ids = [...favorites];
    if (ids.length === 0) {
      setFavoriteItems([]);
      return;
    }
    fetch(`${PRODUCTS_BATCH_URL}?ids=${ids.map(encodeURIComponent).join(',')}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { items: Product[] }) => setFavoriteItems(data.items))
      .catch(() => setFavoriteItems([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewingFavorites]);

  // 최근본도 찜과 동일한 이유로 진입 시 스냅샷만 가져오고, 화면 안에서의
  // 개별 삭제/전체삭제는 아래 렌더에서 recentIds로 다시 필터링해 즉시
  // 반영한다.
  useEffect(() => {
    if (!viewingRecentlyViewed) return;
    if (recentIds.length === 0) {
      setRecentItems([]);
      return;
    }
    fetch(`${PRODUCTS_BATCH_URL}?ids=${recentIds.map(encodeURIComponent).join(',')}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { items: Product[] }) => {
        const byLink = new Map(data.items.map((p) => [p.shareLink, p]));
        setRecentItems(recentIds.map((id) => byLink.get(id)).filter((p): p is Product => p !== undefined));
      })
      .catch(() => setRecentItems([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewingRecentlyViewed]);

  // 주요 기능(앱 상세 화면 바로가기)이 intoss://hidden-deals?view=favorites 같은
  // 링크로 특정 화면을 바로 열 수 있게 한다.
  useEffect(() => {
    const view = new URLSearchParams(window.location.search).get('view');
    if (view === 'favorites') {
      Analytics.click({ log_name: 'deep_link_open', view });
      setViewingFavorites(true);
    } else if (view === 'event') {
      Analytics.click({ log_name: 'deep_link_open', view });
      setViewingEvent(true);
    } else if (view === 'recent') {
      Analytics.click({ log_name: 'deep_link_open', view });
      setViewingRecentlyViewed(true);
    } else if (view === 'ranking') {
      Analytics.click({ log_name: 'deep_link_open', view });
      setViewingRanking(true);
    }
  }, []);

  // 서브뷰(카테고리 상세/찜/이벤트/최근본)에 들어갈 때 history entry를 하나
  // 쌓아서, 플랫폼 자체 상단 뒤로가기 버튼 및 스와이프 제스처가 홈으로
  // 돌아오게 만든다 - 화면에 직접 그린 뒤로가기 버튼과 중복 노출되지 않도록
  // 자체 버튼은 두지 않는다.
  const isSubView =
    selectedCategory !== null || viewingFavorites || viewingEvent || viewingRecentlyViewed || viewingRanking;
  const wasSubView = useRef(false);

  useEffect(() => {
    if (isSubView && !wasSubView.current) {
      window.history.pushState({ hiddenDealsSubView: true }, '');
    }
    wasSubView.current = isSubView;
  }, [isSubView]);

  useEffect(() => {
    const goHome = () => {
      setSelectedCategory(null);
      setViewingFavorites(false);
      setViewingEvent(false);
      setViewingRecentlyViewed(false);
      setViewingRanking(false);
    };
    window.addEventListener('popstate', goHome);
    return () => window.removeEventListener('popstate', goHome);
  }, []);

  const retry = () => {
    setHomeState({ status: 'loading' });
    fetchHomeProducts();
  };

  return (
    <div className="canvas bg-canvas">
      <div className="page-container">
        <header className="page-header">
          <div className="page-header__row">
            <h1>반값 이상 특가</h1>
          </div>
          <div className="search-bar">
            <Search size={18} />
            <input
              type="text"
              className="search-bar__input"
              placeholder="상품명으로 검색"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setVisibleCount(PAGE_SIZE); }}
            />
          </div>
        </header>

        {homeState.status === 'loading' && <p className="state-message">불러오는 중...</p>}

        {homeState.status === 'error' && (
          <div className="state-message">
            <p>상품을 불러오지 못했어요.</p>
            <button type="button" className="retry-button" onClick={retry}>
              다시 시도
            </button>
          </div>
        )}

        {homeState.status === 'ready' && (() => {
          const sortRow = (
            <div className="sort-row">
              <div className="sort-bar__group" role="group" aria-label="정렬">
                {SORT_OPTIONS.map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    className={
                      sort === option.key ? 'sort-bar__item sort-bar__item--active' : 'sort-bar__item'
                    }
                    onClick={() => { setSort(option.key); setVisibleCount(PAGE_SIZE); }}
                  >
                    <span className="sort-bar__item-label">{option.label}</span>
                  </button>
                ))}
              </div>
            </div>
          );

          if (isSearching) {
            if (searchState.status === 'loading') {
              return <p className="state-message">불러오는 중...</p>;
            }
            if (searchState.status === 'error') {
              return <p className="state-message">검색 결과를 불러오지 못했어요.</p>;
            }
            if (searchState.items.length === 0) {
              return <p className="state-message">검색 결과가 없어요.</p>;
            }
            return (
              <>
                {sortRow}
                <div className="product-grid">
                  {searchState.items.map((product) => (
                    <ProductCard
                      key={product.shareLink}
                      product={product}
                      onSelect={handleSelectProduct}
                      isFavorite={favorites.has(product.shareLink)}
                      onToggleFavorite={toggleFavorite}
                    />
                  ))}
                </div>
                {searchState.hasMore && (
                  <button type="button" className="load-more-button" onClick={searchState.loadMore}>
                    더보기
                  </button>
                )}
              </>
            );
          }

          if (viewingEvent) {
            return (
              <TodaysPickEvent
                products={homeState.products}
                onSelect={handleSelectProduct}
                favorites={favorites}
                onToggleFavorite={toggleFavorite}
              />
            );
          }

          if (viewingRecentlyViewed) {
            const recentProducts = recentItems.filter((p) => recentIds.includes(p.shareLink));
            const sortedRecent = sortProducts(recentProducts, sort);
            const visibleRecent = sortedRecent.slice(0, visibleCount);
            return (
              <>
                <div className="recently-viewed-page__header">
                  {recentProducts.length > 0 && (
                    <button
                      type="button"
                      className="recently-viewed-page__clear"
                      onClick={() => {
                        Analytics.click({ log_name: 'recently_viewed_clear_all_click', item_count: recentProducts.length });
                        clearAll();
                      }}
                    >
                      전체 삭제
                    </button>
                  )}
                </div>

                {recentProducts.length === 0 ? (
                  <p className="state-message">아직 본 상품이 없어요.</p>
                ) : (
                  <>
                    {sortRow}
                    <div className="product-grid">
                      {visibleRecent.map((product) => (
                        <ProductCard
                          key={product.shareLink}
                          product={product}
                          onSelect={handleSelectProduct}
                          isFavorite={favorites.has(product.shareLink)}
                          onToggleFavorite={toggleFavorite}
                          onRemove={removeView}
                        />
                      ))}
                    </div>
                    {visibleRecent.length < sortedRecent.length && (
                      <button
                        type="button"
                        className="load-more-button"
                        onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
                      >
                        더보기
                      </button>
                    )}
                  </>
                )}
              </>
            );
          }

          if (viewingRanking) {
            return (
              <PopularRanking
                products={homeState.products}
                onSelect={handleSelectProduct}
              />
            );
          }

          if (viewingFavorites) {
            const favoriteProducts = favoriteItems.filter((p) => favorites.has(p.shareLink));
            const sortedFavorites = sortProducts(favoriteProducts, sort);
            const visibleFavorites = sortedFavorites.slice(0, visibleCount);
            return (
              <>
                {favoriteProducts.length === 0 ? (
                  <p className="state-message">아직 찜한 상품이 없어요.</p>
                ) : (
                  <>
                    {sortRow}
                    <div className="product-grid">
                      {visibleFavorites.map((product) => (
                        <ProductCard
                          key={product.shareLink}
                          product={product}
                          onSelect={handleSelectProduct}
                          isFavorite
                          onToggleFavorite={toggleFavorite}
                        />
                      ))}
                    </div>
                    {visibleFavorites.length < sortedFavorites.length && (
                      <button
                        type="button"
                        className="load-more-button"
                        onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
                      >
                        더보기
                      </button>
                    )}
                  </>
                )}
              </>
            );
          }

          const groups = dailyShuffle(groupByCategory(homeState.products), 'category-order');

          if (selectedCategory === null) {
            const allTimeLowProducts = dailyShuffle(
              dedupeByImage(sortProducts(homeState.products.filter((p) => p.isAllTimeLow), 'recommend')).slice(
                0,
                SHELF_POOL_SIZE
              ),
              'all-time-low'
            ).slice(0, SHELF_SIZE);

            return (
              <>
                <TopDealsCarousel products={homeState.products} onSelect={handleSelectProduct} />

                <p className="daily-update-notice">매일 아침 10시, 더 많은 특가가 추가돼요</p>

                <PushOptInCard />

                <div className="payback-banner">
                  <span className="payback-banner__emoji tf">💸</span>
                  <span className="payback-banner__text">
                    <span className="payback-banner__title">5,000원 이상 구매하고 500원 페이백</span>
                    <span className="payback-banner__subtitle">지금 진행 중인 프로모션이에요, 페이백 받으세요</span>
                  </span>
                </div>

                {allTimeLowProducts.length > 0 && (
                  <div className="category-shelf">
                    <div className="category-shelf__header">
                      <span className="category-shelf__title">
                        <span className="tf">🔥</span> 역대 최저가 상품
                      </span>
                    </div>
                    <div className="category-shelf__list">
                      {allTimeLowProducts.map((product) => (
                        <ProductCard
                          key={product.shareLink}
                          product={product}
                          onSelect={handleSelectProduct}
                          isFavorite={favorites.has(product.shareLink)}
                          onToggleFavorite={toggleFavorite}
                        />
                      ))}
                    </div>
                  </div>
                )}

                <div className="category-grid">
                  {groups.map((group) => (
                    <button
                      key={group.label}
                      type="button"
                      className="category-grid__item"
                      onClick={() => {
                        Analytics.click({ log_name: 'category_icon_click', category: group.label });
                        selectCategory(group.label);
                      }}
                    >
                      <span className="category-grid__emoji tf">
                        {CATEGORY_EMOJI[group.label] ?? DEFAULT_CATEGORY_EMOJI}
                      </span>
                      <span className="category-grid__label">{group.label}</span>
                    </button>
                  ))}
                  <button
                    type="button"
                    className="category-grid__item"
                    onClick={() => {
                      Analytics.click({ log_name: 'event_grid_tile_click' });
                      openEvent();
                    }}
                  >
                    <span className="category-grid__emoji tf">🎉</span>
                    <span className="category-grid__label">오늘의 특가 이벤트</span>
                  </button>
                </div>

                {groups.map((group) => (
                  <div className="category-shelf" key={group.label}>
                    <div className="category-shelf__header">
                      <span className="category-shelf__title">
                        <span className="tf">{CATEGORY_EMOJI[group.label] ?? DEFAULT_CATEGORY_EMOJI}</span>{' '}
                        {group.label} 특가 순위
                      </span>
                      <button
                        type="button"
                        className="category-shelf__more"
                        onClick={() => {
                          Analytics.click({ log_name: 'category_shelf_more_click', category: group.label });
                          selectCategory(group.label);
                        }}
                      >
                        전체보기
                      </button>
                    </div>
                    <div className="category-shelf__list">
                      {dailyShuffle(
                        dedupeByImage(sortProducts(group.products, 'recommend')).slice(0, SHELF_POOL_SIZE),
                        `shelf-${group.label}`
                      )
                        .slice(0, SHELF_SIZE)
                        .map((product) => (
                          <ProductCard
                            key={product.shareLink}
                            product={product}
                            onSelect={handleSelectProduct}
                            isFavorite={favorites.has(product.shareLink)}
                            onToggleFavorite={toggleFavorite}
                          />
                        ))}
                    </div>
                  </div>
                ))}

                <BannerAd />
              </>
            );
          }

          const activeGroup = groups.find((g) => g.label === selectedCategory);

          if (categoryState.status === 'loading') {
            return (
              <>
                <nav className="category-tabs" aria-label="카테고리">
                  {groups.map((group) => (
                    <button
                      key={group.label}
                      type="button"
                      className={
                        group.label === activeGroup?.label
                          ? 'category-tabs__item category-tabs__item--active'
                          : 'category-tabs__item'
                      }
                      onClick={() => {
                        Analytics.click({ log_name: 'category_tab_click', category: group.label });
                        selectCategory(group.label);
                      }}
                    >
                      {group.label}
                    </button>
                  ))}
                </nav>
                <p className="state-message">불러오는 중...</p>
              </>
            );
          }

          if (categoryState.status === 'error') {
            return <p className="state-message">카테고리 상품을 불러오지 못했어요.</p>;
          }

          if (categoryState.items.length === 0) {
            return <p className="state-message">지금은 조건에 맞는 상품이 없어요.</p>;
          }

          return (
            <>
              <nav className="category-tabs" aria-label="카테고리">
                {groups.map((group) => (
                  <button
                    key={group.label}
                    type="button"
                    className={
                      group.label === activeGroup?.label
                        ? 'category-tabs__item category-tabs__item--active'
                        : 'category-tabs__item'
                    }
                    onClick={() => {
                      Analytics.click({ log_name: 'category_tab_click', category: group.label });
                      selectCategory(group.label);
                    }}
                  >
                    {group.label}
                  </button>
                ))}
              </nav>

              {sortRow}

              <div className="product-grid">
                {categoryState.items.map((product) => (
                  <ProductCard
                    key={product.shareLink}
                    product={product}
                    onSelect={handleSelectProduct}
                    isFavorite={favorites.has(product.shareLink)}
                    onToggleFavorite={toggleFavorite}
                  />
                ))}
              </div>
              {categoryState.hasMore && (
                <button type="button" className="load-more-button" onClick={categoryState.loadMore}>
                  더보기
                </button>
              )}
            </>
          );
        })()}

        <p className="disclosure">
          이 앱은 토스쇼핑 파트너스 활동의 일환으로,
          <br />
          상품 구매 시 일정액의 수수료를 제공받습니다.
        </p>
      </div>

      <div className="quick-nav-pill">
        <button type="button" className="quick-nav-pill__item" onClick={openHome}>
          <span className="tf quick-nav-pill__icon">🏠</span>
          <span className="quick-nav-pill__label">홈</span>
        </button>
        <button type="button" className="quick-nav-pill__item" onClick={openRanking}>
          <span className="tf quick-nav-pill__icon">👑</span>
          <span className="quick-nav-pill__label">랭킹</span>
        </button>
        <button
          type="button"
          className="quick-nav-pill__item"
          data-active={favorites.size > 0}
          onClick={openFavorites}
        >
          <Heart size={18} filled={favorites.size > 0} />
          <span className="quick-nav-pill__label">찜</span>
          {favorites.size > 0 && <span className="quick-nav-pill__badge">{favorites.size}</span>}
        </button>
        {recentIds.length > 0 && (
          <button type="button" className="quick-nav-pill__item" onClick={openRecentlyViewedPage}>
            <Bag size={18} />
            <span className="quick-nav-pill__label">최근본</span>
          </button>
        )}
      </div>

      {selectedProduct && (
        <PurchaseSheet product={selectedProduct} onClose={() => setSelectedProduct(null)} />
      )}
    </div>
  );
}

export default App;
```

- [ ] **Step 2: 타입체크로 검증**

Run: `cd deep-discount-deals && npx tsc -b`
Expected: 에러 없이 종료

- [ ] **Step 3: 로컬 개발 서버로 수동 확인**

Run: `cd deep-discount-deals && npm run dev` (백그라운드로 실행)

브라우저로 열어서 확인: 홈 화면 캐러셀/역대최저가/카테고리 진열대가
보이는지, 카테고리 "전체보기" 클릭 시 상품이 로드되고 "더보기"가
동작하는지, 검색창에 타이핑 후(300ms 대기) 결과가 뜨는지, 랭킹/오늘의
특가 이벤트가 채워지는지, 찜/최근본 화면이 뜨는지. 개발 서버는 확인 후
종료.

- [ ] **Step 4: 커밋**

```bash
git add deep-discount-deals/src/App.tsx
git commit -m "Rewire App.tsx to fetch per-view from DB-backed APIs instead of one full catalog"
```

---

### Task 7: 배포 후 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 푸시해서 Vercel 배포 반영**

Run: `git push`

- [ ] **Step 2: 배포 반영 대기 후 새 엔드포인트 확인**

Run(배포 완료까지 폴링): `until [ "$(curl -sS -o /dev/null -w '%{http_code}' https://shaerlink.vercel.app/api/products/home)" = "200" ]; do sleep 3; done`

Run: `curl -sS --compressed "https://shaerlink.vercel.app/api/products/batch?ids=<실제_shareLink_1>,<실제_shareLink_2>" | python3 -m json.tool`
(`<실제_shareLink_*>`는 `curl -sS https://shaerlink.vercel.app/api/products/home`
응답에서 아무 `shareLink` 값 2개를 가져다 쓴다)
Expected: `{"items": [...]}` — 요청한 shareLink들의 상품 정보가 정확히
돌아옴

- [ ] **Step 3: 구 전체덤프 라우트가 제거됐는지 확인**

Run: `curl -sS -w "\n%{http_code}\n" "https://shaerlink.vercel.app/api/products"`
Expected: `400`과 `{"error": "category or search is required"}` (더 이상
파일 기반 전체 덤프를 반환하지 않음)

- [ ] **Step 4: 실제 앱 화면 확인**

토스 앱에서 미니앱을 열어(또는 `npm run dev`로 로컬에서) 홈/카테고리
전체보기/검색/랭킹/오늘의 특가 이벤트/찜/최근본 화면이 전부 정상 동작하는지
확인. 특히 찜/최근본에 있던 상품이 화면에 뜨는지(배치 조회가 실제로
맞는 상품을 가져오는지) 확인.

- [ ] **Step 5: CI 파이프라인 무변화 확인**

Run: `python3 -c "import json; print(len(json.load(open('app-data/products.json', encoding='utf-8'))))"`
Expected: 에러 없이 상품 개수 출력(파일이 여전히 정상적으로 존재하고
읽힘 — `.github/workflows/refresh-data.yml`의 안전장치가 계속 동작함을
간접 확인)
