# 상품 카탈로그 DB 전환 설계

## 배경

지금 상품 데이터는 `build_app_data.py`가 쉐어링크 API에서 받아와
`app-data/products.json`(전체) + `app-data/products-home.json`(홈 화면용
작은 서브셋)으로 저장하고, git에 커밋해서 Vercel(`api/webhook.py`)이 정적
파일로 서빙한다. 홈은 작은 서브셋을 먼저 받고 전체 카탈로그는 백그라운드로
받아 교체하는 구조(2026-09-22 도입)로, 첫 로딩 시간과 카탈로그 크기를
분리했다.

근데 이 프로젝트는 장기적으로 계속 운영되고, 매일 API로 아이템이 계속
추가되기만 하는 구조다. 게다가 나중에 같은 프로젝트에 **쿠팡파트너스를
두 번째 데이터 소스로 추가**할 계획이 있다. 이 두 가지 전제 때문에:

1. git에 JSON 파일로 커밋하는 방식은 매일 갱신이 쌓이면서 저장소 역사가
   무한히 커진다.
2. 검색/카테고리 조회가 지금은 클라이언트가 전체 배열을 메모리에 들고
   필터링하는 방식이라, 카탈로그가 커질수록 클라이언트가 받아야 하는
   데이터도 무한히 커진다.
3. 소스가 둘(쉐어링크, 쿠팡파트너스)이 되면 지금 구조로는 서빙 계층을
   소스별로 다시 손봐야 한다.

이 설계는 저장소를 실제 DB(Postgres, Neon)로 옮기고, 조회를 "전체를 받아서
클라이언트가 거른다"에서 "필요한 만큼만 서버에 쿼리한다"로 바꾼다.

## 목표

- 카탈로그 크기가 커져도(수만 개 이상) 홈 화면 로딩 시간에 영향 없음
- 카테고리 조회/검색이 서버 쿼리 기반 페이지네이션으로 동작
- 나중에 쿠팡파트너스 같은 다른 소스를 추가할 때 서빙 계층(API)을 다시
  설계하지 않아도 되게, 스키마에 `source` 컬럼을 둬서 대비
- 기존 화면 동작(홈 화면 구성, 카드 UI, 정렬 옵션)은 그대로 유지 — 데이터
  가져오는 방식만 바뀜

## 비목표

- 쿠팡파트너스 연동 자체 (이번엔 스키마만 대비하고, 실제 연동은 나중 별도
  프로젝트)
- 실시간 동기화 (지금처럼 하루 단위 배치 갱신 유지)
- 인증/유저별 데이터 (여전히 공개 카탈로그 조회만)
- DB 마이그레이션 프레임워크 도입 — 테이블 하나짜리 스키마라 수동 DDL 한 번으로 충분

## 아키텍처

```
[데이터 파이프라인]
build_app_data.py (쉐어링크 API 호출은 기존과 동일)
  → 지금처럼 app_data 리스트 생성
  → JSON 파일 쓰기 대신 Postgres UPSERT
    (source, source_item_id) 충돌 시 UPDATE

[API — api/webhook.py]
GET /api/products/home
  → DB에서 카테고리별 상위 N + all-time-low + 캐러셀 후보 쿼리 (지금의
    build_home_subset 로직을 SQL로)
GET /api/products?category=X&sort=recommend&cursor=...
  → 카테고리 페이지네이션 조회
GET /api/products?search=Y&cursor=...
  → pg_trgm 기반 부분일치 검색, 페이지네이션
GET /api/products (기존 전체 덤프)
  → 1단계 동안 하위 호환으로 유지, 2단계에서 제거

[프론트엔드 — App.tsx]
홈: 지금과 동일한 컴포넌트 구조, fetch 대상만 DB 기반 API로 바뀜(눈에 보이는
변화 없음)
검색 / 카테고리 "전체보기": 로드된 배열을 필터링하던 방식 →
쿼리 API 호출 + "더보기"가 다음 커서 페이지를 가져오는 방식으로 교체
"백그라운드로 전체 카탈로그 받기" 로직 제거 (더 이상 필요 없음)
```

## 스키마

```sql
create extension if not exists pg_trgm;

create table products (
  source          text not null,           -- 'sharelink' | 'coupang'(예정)
  source_item_id  text not null,           -- tacaItemId 등 소스별 원본 id
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
);

create index products_category_idx on products (category);
create index products_name_trgm_idx on products using gin (name gin_trgm_ops);
create index products_review_count_idx on products (review_count desc);
```

## 컴포넌트

### `build_app_data.py` 변경
- `to_app_data()` 결과(`data` 리스트)를 JSON 파일에 쓰던 부분을 DB
  upsert로 교체
- `psycopg2` 신규 의존성 추가 (`requirements.txt`)
- `PRODUCTS_DB_DATABASE_URL` 환경변수로 접속(Vercel Neon 연동이 자동 주입)
- 로컬 실행 시에도 같은 접속 문자열이 필요 — `.env`에 추가

### `api/webhook.py` 변경
- `_handle_products_request`가 파일 읽기 대신 DB 쿼리로 응답 생성
- 새 쿼리 파라미터 파싱(`category`, `search`, `sort`, `cursor`, `limit`)
  — `sort`는 클라이언트의 기존 `SORT_OPTIONS`와 동일하게 `recommend`(review_count
  desc) / `discount`(discount_rate desc) / `price`(price asc) 3종
- 커서 페이지네이션: OFFSET 방식은 카탈로그가 커지면 느려지므로 keyset
  방식을 쓴다 — 정렬 컬럼 + `(source, source_item_id)`를 동점 처리용 타이
  브레이커로 묶은 복합 키 기준(예: `sort=recommend`면
  `(review_count, source, source_item_id)`, `sort=price`면
  `(price, source, source_item_id)`). 정렬 기준이 바뀌면 커서의 키도 그
  기준을 따라가야 한다.

### `App.tsx` 변경
- 검색 입력 → 디바운스 후 `/api/products?search=` 호출, 결과 누적
- 카테고리 "전체보기" → `/api/products?category=` 호출, "더보기" 버튼이
  다음 커서 요청
- `state.products`가 더 이상 "전체 카탈로그"를 의미하지 않음 — 홈 서브셋 /
  검색 결과 / 카테고리 결과를 각각 별도 상태로 분리

## 진행 순서

1. **1단계(기초, 이번 스펙의 범위)**: DB 스키마 생성, 파이프라인 DB
   upsert로 전환, 새 쿼리 API 3종 추가. 기존 `/api/products`(전체 덤프)와
   프론트엔드는 손대지 않아 화면 동작 무변화. 별도 검증: DB에 데이터가
   정상적으로 들어갔는지, 새 API가 올바른 결과를 반환하는지 pytest로 확인.
2. **2단계(다음 스펙)**: `App.tsx`의 검색/카테고리 뷰를 새 API 기반으로
   리팩터링, 백그라운드 전체 로딩 로직 제거, 기존 `/api/products` 전체
   덤프 엔드포인트 및 `products.json`/`products-home.json` 파일 정리.

## 이미 완료된 준비 작업

- Neon Postgres 생성 및 Vercel 프로젝트 연결 완료 (prefix `PRODUCTS_DB`,
  Free 티어, `shaerlink-products-db`)
