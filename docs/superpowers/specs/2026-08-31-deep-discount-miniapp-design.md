# 반값특가 앱인토스 미니앱 설계

## 배경

기존 Phase 1(`docs/superpowers/specs/2026-08-28-daily-deal-content-bot-design.md`)은
하루특가 상품을 스크래핑해서 SNS(쓰레드/틱톡/유튜브)용 콘텐츠를 만드는 개인 봇이다.
이번 서브프로젝트는 별도의 새로운 유통 채널이다: **토스 앱 안에서 실행되는
"앱인토스(App-in-Toss)" 미니앱**을 만들어, 할인율 50% 이상 상품을 그리드로
보여주고 탭하면 바로 제휴 링크(쉐어링크)로 이동시켜 구매를 유도한다.

기존 Python 스크래핑 파이프라인(`scrape.py`)은 실전에서 이미 검증됐다 (30일
최저가 필터로 117개 상품 스크래핑 + 링크 발급 성공). 이 서브프로젝트는 그
파이프라인을 그대로 재사용하는 데이터 소스로 삼고, 완전히 새로운 프론트엔드
(앱인토스 미니앱)를 추가한다.

## 목표

- 기존 스크래퍼로 수집한 상품 중 **할인율 50% 이상**만 걸러서 정적
  `products.json`으로 만들고, 매일 갱신해서 GitHub(raw.githubusercontent.com)에
  올린다
- 앱인토스 미니앱(React + TypeScript + Vite, 공식 `create-ait-app` 스캐폴딩)이
  그 JSON을 fetch해서, 할인율 높은 순으로 정렬된 카드 그리드를 보여준다
- 카드를 탭하면 바로 쉐어링크(shortUrl)를 열어서 토스쇼핑 상품 페이지로 이동시킨다
- 검색/카테고리 필터/카운트다운 등은 넣지 않는다 — 사진+할인율 배지+가격+상품명
  카드 그리드 하나로 최대한 간결하게

## 비목표

- 실시간 데이터 (하루 1회 수동 갱신, 나중에 자동화 가능)
- 카테고리 필터, 검색, 정렬 옵션 UI (할인율 내림차순 고정)
- 앱인토스 로그인/결제 등 SDK의 다른 기능 연동
- 백엔드 서버 (정적 JSON 파일 하나로 충분)
- 기존 Phase 1의 SNS 캡션 생성 파이프라인(`main.py`)은 건드리지 않음 — 완전히
  별도의 새 스크립트로 추가

## 아키텍처

```
[데이터 파이프라인 — 기존 Python 프로젝트 확장]
scrape.py의 run_scrape() (변경 없이 재사용)
  → 새 build_app_data.py 스크립트가 filter_fn으로 "할인율 >= 50%"만 걸러서 호출
  → app-data/products.json 생성 (name/price/discountRate/imageUrl/shareLink만,
    할인율 내림차순 정렬)
  → 사람이 git add/commit/push (수동, Phase 1의 "SNS는 사람이 수동 포스팅"과
    같은 원칙 — 나중에 신뢰가 쌓이면 자동 push 추가 가능)
  → raw.githubusercontent.com/<user>/shaerlink/main/app-data/products.json 로
    공개 서빙 (레포를 public으로 전환 필요)

[프론트엔드 — 새 서브프로젝트, 앱인토스 미니앱]
shaerlink/miniapp/ 에 /ait:new 로 스캐폴딩 (react-ts 템플릿, devtools 자동 배선
→ 토스 앱 없이 브라우저에서 바로 프리뷰 가능)
  → 화면 1개: 마운트 시 위 raw GitHub URL fetch
  → 할인율 내림차순 카드 그리드 (이미지, "N% 특가" 배지, 가격, 상품명)
  → 카드 탭 → shareLink 새 창/네비게이션으로 열기
```

## 컴포넌트

### scrape.py 변경 (기존 파일에 최소 추가)

- `run_scrape(profile_dir, output_dir, filter_fn=None)` — `filter_fn` 파라미터
  추가. 파싱된 상품 목록에 대해 링크 발급(버튼 클릭) *전에* `filter_fn`을 적용해서,
  필터를 통과한 상품에 대해서만 링크를 발급한다 (불필요한 사이트 상호작용 방지).
  `filter_fn=None`이면 기존 Phase 1 동작(`main.py`)과 완전히 동일 — 하위 호환.
- 필터 후 상품이 0개면 기존과 동일하게 `RuntimeError`로 중단.

### build_app_data.py (신규)

- 입력: 없음 (스크래핑은 `run_scrape`가 처리)
- 처리: `run_scrape(PROFILE_DIR, output_dir, filter_fn=상품 discountRate >= 50)`
  호출 → 결과를 `{name, price, discountRate, imageUrl, shareLink}` 필드만 남기고
  할인율 내림차순 정렬
- 출력: `app-data/products.json`
- 에러 처리: `run_scrape`가 던지는 에러(로그인 만료, 상품 0개, 필터 후 0개)를
  그대로 사용자에게 보여주고 종료 (Phase 1의 `main.py`와 동일한 원칙)

### 미니앱 (신규 서브프로젝트, `shaerlink/miniapp/`)

- 스캐폴딩: `/ait:new` 스킬로 공식 `create-ait-app` CLI 실행 (react-ts 템플릿),
  devtools 자동 배선 — 로컬 브라우저에서 `npm run dev`로 바로 확인 가능
- 데이터: 마운트 시 `fetch(GITHUB_RAW_URL)` → JSON 파싱 → 할인율 내림차순
  정렬(이미 정렬돼서 오지만 방어적으로 한 번 더)
- 화면: 카드 그리드 (이미지, "N% 특가" 배지, 가격, 상품명 — 검색/필터/카운트다운
  없음). 디자인은 앱인토스 스캐폴딩이 자동으로 심어주는 디자인 가이드(토큰,
  아이콘셋)를 기반으로 하고, 필요하면 `ui-ux-pro-max` 스킬로 다듬는다
- 상호작용: 카드 탭 → `shareLink` 열기 (정확한 SDK 호출 방식은 앱인토스 문서
  MCP로 구현 시점에 확인)
- 에러 처리: fetch 실패 시 "상품을 불러오지 못했어요" 같은 빈 상태 화면 (재시도
  버튼 정도, 과하게 만들지 않음)

## 에러 처리 정리

| 상황 | 동작 |
|---|---|
| `build_app_data.py` 실행 중 로그인 만료/상품 0개 | `run_scrape`가 던지는 에러 그대로 노출, 중단 |
| 필터(할인율 50%+) 후 상품이 0개 | 에러로 중단 (조용히 빈 JSON 만들지 않음) |
| 미니앱에서 JSON fetch 실패 | 빈 상태 화면 표시, 앱이 죽지 않음 |
| 개별 상품 이미지 로드 실패 | 브라우저 기본 깨진 이미지 처리에 맡김 (과설계 안 함) |

## 테스트

- `run_scrape`의 `filter_fn` 파라미터: 순수 함수 부분(필터 적용 로직)은 기존
  `tests/test_scrape.py` 스타일로 단위 테스트 가능 (실제 클릭 루프는 여전히
  라이브 검증 필요 — Phase 1과 동일한 한계)
- `build_app_data.py`의 슬림화/정렬 로직: 순수 함수로 분리해서 단위 테스트
- 미니앱: 컴포넌트 단위 테스트보다는 로컬 브라우저(devtools)로 직접 확인 —
  앱인토스 자체 테스트 도구(`test-on-device`, `setup-debugger` 스킬)를 활용

## 기술 스택

- 데이터 파이프라인: 기존과 동일 (Python + Playwright + BeautifulSoup)
- 미니앱: React + TypeScript + Vite, 공식 `@apps-in-toss` 툴체인
  (`create-ait-app`, `@apps-in-toss/devtools`)
- 정적 데이터 호스팅: GitHub raw content (별도 백엔드 없음)

## 결정 필요/보류 사항

- GitHub 레포를 public으로 전환하는 것은 되돌리기 번거로운 가시성 변경이라,
  스펙 승인과 별개로 **실행 직전에 한 번 더 확인**한다.
- shareLink를 여는 정확한 앱인토스 SDK 호출(예: 외부 브라우저 오픈 API 이름)은
  구현 단계에서 `apps-in-toss-docs` MCP로 확인하고 사용한다 — 지금 시점에는
  API 이름을 추측하지 않는다.
