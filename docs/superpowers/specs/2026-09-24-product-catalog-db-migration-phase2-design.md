# 상품 카탈로그 DB 전환 — 2단계 설계

## 배경

1단계(`docs/superpowers/specs/2026-09-23-product-catalog-db-migration-design.md`)에서
Postgres(Neon)에 상품 데이터를 upsert하고, DB 기반 쿼리 API 3종
(`/api/products/home`, `/api/products?category=`, `/api/products?search=`)을
추가했다. 단, 1단계는 기존 `/api/products`(전체 덤프) 엔드포인트와
`App.tsx`를 그대로 두어 화면 동작 무변화를 유지했다 — 배포 검증까지 완료됨.

2단계는 `App.tsx`가 새 DB 기반 API만으로 동작하도록 리팩터링하고, 이제
쓸모없어진 구 엔드포인트와 죽은 파일들을 정리한다. 이 프로젝트는 장기적으로
운영하며 후반에는 동일 구조를 쿠팡파트너스 데이터 소스로 확장할 계획이라,
프론트엔드가 "전체 카탈로그를 한 번에 내려받아 클라이언트에서 다 처리"하는
현재 방식에서 벗어나 서버 쿼리 기반으로 가는 것이 이번 스펙의 목적이다.

## 목표

- `App.tsx`의 모든 화면(홈/카테고리/검색/랭킹/이벤트/찜/최근본)이 전체
  카탈로그를 한 번에 들고 있지 않고, 화면별로 필요한 만큼만 서버에 요청한다
- 기존 `/api/products`(전체 덤프) 엔드포인트와 백그라운드 전체 카탈로그
  fetch 로직을 제거한다
- 화면에 보이는 동작(정렬 옵션, "더보기" 페이지네이션, 검색 결과, 랭킹/이벤트
  내용)은 사용자 입장에서 기존과 동일하게 유지한다

## 비목표

- 쿠팡파트너스 데이터 소스 통합 (이후 별도 스펙)
- 새로운 화면/기능 추가
- 디자인/UI 변경

## 발견된 숨은 복잡도

1단계 스펙은 "검색 + 카테고리 전체보기"만 옮기면 된다고 가정했으나, 실제
`App.tsx` 조사 결과 `state.products`(현재 전체 카탈로그)를 쓰는 화면이 더
많았다:

- **`PopularRanking`**: 전체 카탈로그에서 리뷰순 상위 30개(이미지 기준
  dedup) — 카테고리 무관 전역 집계
- **`TodaysPickEvent`**: 위와 동일한 선택 로직(리뷰순 정렬 + dedup)으로
  상위 10개 — 두 컴포넌트 모두 넘겨받은 `products` 배열에서 자체적으로
  정렬·dedup·슬라이스를 수행하며, 이름과 달리 할인율이 아니라 리뷰수 기준
- **찜(즐겨찾기) / 최근 본 상품**: 사용자가 과거에 본 임의의 상품을
  `shareLink`로 다시 조회해야 함 — 카테고리/검색 API로는 해결 안 됨

## 아키텍처

### 백엔드 (`api/webhook.py`)

**`/api/products/home` 확장**: 기존 홈 쿼리(카테고리별 top-N + 역대최저가 +
고할인 풀을 `UNION ALL`로 합쳐 `share_link` 기준 dedup한 평평한 배열)에
**전역 리뷰순 top-30 풀**을 하나 더 `UNION`으로 추가한다. 응답 shape는
그대로(평평한 배열) 유지 — `PopularRanking`/`TodaysPickEvent`는 넘겨받은
배열에서 정렬·dedup·슬라이스를 스스로 하므로, 배열에 전역 top-30이
보장되기만 하면 프론트 컴포넌트 코드를 전혀 수정할 필요가 없다.

**신규 엔드포인트 `/api/products/batch?ids=<shareLink1>,<shareLink2>,...`**:
`WHERE share_link = ANY(%s)` 조회로 찜/최근본이 필요로 하는 임의 상품을
가져온다. 순서는 보장하지 않음(프론트에서 로컬에 저장된 순서대로 재배열).
존재하지 않는 `shareLink`는 결과에서 조용히 빠진다(에러 아님).

**`/api/products`(전체 덤프) 라우트 제거**: `_handle_products_request`
메서드, `PRODUCTS_JSON_PATH`/`PRODUCTS_HOME_JSON_PATH` 상수,
`from pathlib import Path` import(다른 용도로 안 쓰임 확인됨)를 삭제한다.
`do_GET`의 `/api/products` 분기는 쿼리 파라미터 유무로 나누던 걸 없애고
항상 `_handle_products_page_request()`로 보낸다 — 파라미터가 없으면 그
안에서 이미 `400 {"error": "category or search is required"}`를 반환하므로
동작이 일관된다.

### 파이프라인 (`build_app_data.py`)

`build_home_subset()` 함수와 `HOME_DATA_PATH`(`products-home.json`) 쓰기를
삭제한다. 홈 API는 이미 SQL(`fetch_home_products`)로 직접 계산하므로 이
함수의 산출물은 현재도 아무도 읽지 않는 죽은 파일이었다(`api/webhook.py`의
`PRODUCTS_HOME_JSON_PATH` 상수도 미사용으로 확인됨).

`APP_DATA_PATH`(`products.json`) 쓰기는 **그대로 유지**한다 —
`.github/workflows/refresh-data.yml`이 이 파일의 상품 개수를 전날과
비교해서 데이터가 비정상적으로 줄면 롤백하는 안전장치로 쓰고 있어서, API로
서빙하는 것과 무관하게 파이프라인 자체에 필요하다.

### 프론트엔드 (`deep-discount-deals/src/App.tsx`)

**상태 구조**: `state.products` 하나로 모든 화면을 처리하던 것을 화면별로
분리한다.

```
homeState      : LoadState  // /api/products/home 한 번만 fetch, 기존 유지
                             // (캐러셀/역대최저가/카테고리그리드+진열대/랭킹/이벤트가 전부 이걸 씀)
categoryState  : { items: Product[]; nextCursor: string | null; status: 'loading' | 'error' | 'ready' }
searchState    : { items: Product[]; nextCursor: string | null; status: 'loading' | 'error' | 'ready' }
favoriteItems  : Product[]  // 찜 화면 진입 시 배치 조회, favorites Set 바뀔 때만 재조회
recentItems    : Product[]  // 최근본 화면 진입 시 배치 조회, recentIds 바뀔 때만 재조회
```

**공용 페이지네이션 훅**: 카테고리 전체보기와 검색은 모양이 동일(커서
페이지네이션 + 정렬 + "더보기")하므로 하나의 훅으로 묶는다.

```ts
function usePaginatedProducts(params: { category?: string; search?: string; sort: SortKey }) {
  // category/search/sort 중 하나라도 바뀌면 커서를 리셋하고 1페이지부터 새로 fetch
  // loadMore() 호출 시 저장된 nextCursor로 다음 페이지를 fetch해 items에 append
  return { items, nextCursor, status, loadMore };
}
```

**찜/최근본**: 페이지네이션 없이 배치 조회 1회(최근본은 20개 cap, 찜도
현실적으로 소량). 정렬은 지금처럼 클라이언트에서 기존 `sortProducts()`
재사용.

**검색 입력**: 디바운스(300ms) 후 `searchState` 트리거 — 타이핑마다 즉시
필터링하지 않는다.

**삭제되는 것들**: `DATA_URL` 상수, `fetchProducts()`의 전체 카탈로그
백그라운드 fetch(`.then(fetchJson(DATA_URL)...)`) 체인.

**안 건드리는 것들**: `groupByCategory`/`dailyShuffle`/`dedupeByImage`는
홈 화면(`homeState`)에서 계속 사용. `PopularRanking`/`TodaysPickEvent`
컴포넌트 내부 로직은 무변화(홈 API가 필요한 데이터를 이미 포함해서 넘겨줌).

## 부수 효과

지금은 전체 카탈로그 백그라운드 fetch 실패를 조용히 무시(`.catch(() => {})`)해서
화면별 에러가 드러나지 않았다. 상태를 화면별로 분리하면 각 화면이 자신의
로딩/에러를 정확히 표시하게 되는데, 이는 상태 분리의 당연한 부수 효과다.

## 테스트

1단계와 동일한 TDD 패턴 유지:

- **배치 조회 API**: `WHERE share_link = ANY(...)` SQL과 결과 매핑을 단위
  테스트로 검증. 존재하지 않는 `shareLink`가 섞여도 나머지는 정상 반환되는
  케이스 포함
- **홈 API 전역 top-30 풀**: 한 카테고리에 리뷰수 최상위 항목이 몰려 있어도
  전역 top-30에서 빠지지 않는 케이스를 테스트로 검증
- **프론트 `usePaginatedProducts` 훅**: `deep-discount-deals`에는 React
  테스트 프레임워크가 없음(확인됨) — 이 훅 하나를 위해 새로 도입하지 않고,
  배포 후 curl 검증(1단계 Task 6과 동일한 방식) + 브라우저 수동 확인으로
  갈음한다
- 삭제되는 코드(`_handle_products_request`, `build_home_subset`)는 기존에
  이를 직접 겨냥한 테스트가 없어(확인됨) 별도 "삭제 확인" 테스트 불필요

## 롤아웃

1단계와 동일하게 별도 브랜치 없이 `main`에 직접, 작업 단위로 커밋한다.
프론트/백엔드가 같은 배포에 강결합돼 있어 단계적 피처 플래그 없이 한 번에
전환하고, 배포 직후 1단계 Task 6과 같은 방식(curl + 실제 화면 확인)으로
검증한다.
