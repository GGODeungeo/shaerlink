# 인앱 피드백 리워드 — 설계

## 배경

토스쇼핑 상품에 대한 리뷰는 우리 앱 밖(토스쇼핑)에서 작성되기 때문에 감지할
방법이 없고, 미니앱 자체에 대한 별점/후기(콘솔 "평점 및 리뷰")는 익명 집계라
작성자를 특정 유저에게 연결할 API가 없다(둘 다 확인됨). 대신 앱 안에 직접
"한 줄 피드백" 제출 기능을 만들고, 제출 시 소액을 즉시 리워드한다 — 기존
`grant_click_reward`(클릭 리워드) 흐름과 동일한 모양이다.

## 목표

- 유저가 앱 자체에 대한 짧은 피드백을 남기면 20원을 즉시 받는다
- 한 사람(`anonKey` 기준)은 평생 한 번만 리워드를 받는다
- 스팸/도배성 제출(예: "ㅁㅁㅁ")을 최소한으로 막는다

## 비목표

- 피드백을 앱 안에서 보여주는 화면(관리자용/유저용 모두)
- 토스쇼핑 상품 리뷰 감지·리워드
- 미니앱 평점(별점) 리워드 — API 한계로 애초에 불가능(확인됨)
- 피드백 내용에 대한 욕설·스팸 필터링(텍스트 품질 검증) — 글자 수 검사만

## 아키텍처

### DB (`init_db.py`)

`products` 테이블과 같은 DB에 새 테이블을 추가한다:

```sql
create table if not exists app_reviews (
    anon_key    text primary key,
    body        text not null,
    created_at  timestamptz not null default now()
)
```

`anon_key`를 기본키로 잡아서 같은 사람의 재제출이 자연스럽게 막힌다 — 별도
in-memory 세트나 애플리케이션 레벨 잠금이 필요 없다(`_processed_order_ids`
같은 방식은 콜드 스타트에 초기화되는 문제가 있어 여기선 안 씀).

### 백엔드 (`api/webhook.py`)

새 함수 `submit_review(conn, anon_key: str, body: str) -> bool`:
- `insert into app_reviews (anon_key, body) values (%s, %s) on conflict (anon_key) do nothing`
- 실제로 삽입됐는지(`cur.rowcount == 1`)를 반환 — 이미 있으면 `False`

새 핸들러 `_handle_review_request`(POST `/api/review`):
- body에서 `anonKey`, `text`를 읽는다
- `len(text.strip()) < 10`이면 `400 {"error": "text must be at least 10 characters"}`
- `submit_review()`가 `True`(새 제출)면 `grant_reward(anon_key, 20, promotion_code=os.environ["REVIEW_PROMOTION_CODE"])` 호출(성공/실패 결과는 `grant_click_reward`처럼 로그만 남기고 응답에 영향 없음 — 리워드 지급 실패가 피드백 제출 자체를 실패로 만들면 안 됨)
- `submit_review()`가 `False`(이미 제출함)면 리워드 호출 없이 그대로 진행
- 두 경우 모두 `200 {"received": true}` 반환 — 유저 입장에서 "이미 냈다"는 에러가 아니라 그냥 성공

`do_POST`에 `/api/review` 분기 추가.

### 프론트 (`deep-discount-deals/src`)

- `useReviewPrompt.ts`(신규, `useFavorites.ts`와 동일 패턴): localStorage
  키 `hidden-deals:review-submitted`(boolean)로 "이미 제출했는지"를 추적.
  제출 성공 시 `true`로 기록 — 서버 재확인 없이 카드가 사라진다.
- `ReviewPromptCard.tsx`(신규, `PushOptInCard.tsx`와 같은 모양의 배너
  컴포넌트): 제목("숨은특가 어때요? 한 줄 남기고 20원 받기") + textarea +
  제출 버튼. 10자 미만이면 제출 버튼 비활성화(서버 400을 굳이 안 받게).
  제출 중 상태(로딩)와 실패 시 재시도 가능하게 처리.
- `App.tsx`: 홈 화면(`selectedCategory === null` 분기)에서 `PushOptInCard`
  바로 아래에 `useReviewPrompt`가 "아직 제출 안 함"일 때만
  `<ReviewPromptCard />` 렌더링.

### 프로모션

콘솔에 새 CONVERSION 타입 프로모션 생성("미션 진행하고 포인트 받기"):
`maxSingleRewardAmount` 20원, `dailyUserRewardLimitAmount` 20원(1인 1회
한도와 동일하게 — 어차피 DB가 재지급을 막으므로 이 값 자체는 안전장치일
뿐). 새 환경변수 `REVIEW_PROMOTION_CODE`에 발급된 코드를 저장한다(기존
`PROMOTION_CODE`/`CLICK_PROMOTION_CODE`와 동일한 위치).

## 테스트

TDD, 기존 패턴 그대로:

- `submit_review()`: 첫 제출은 `True` + `app_reviews`에 행 생성, 같은
  `anon_key`로 재제출은 `False` + 행 개수 변화 없음(live-DB 테스트,
  `tests/test_webhook.py`의 `db_conn` 픽스처 재사용, `source`가 아니라
  `anon_key`로 정리하는 것만 다름 — 테스트 종료 시
  `delete from app_reviews where anon_key = 'test-...'`)
- `_handle_review_request`: 10자 미만 400, 10자 이상 첫 제출 200 + 리워드
  호출 확인(모킹), 재제출 200 + 리워드 호출 안 됨(모킹으로 확인)
- 프론트: React 테스트 프레임워크 없음(기존과 동일) — `npx tsc -b` +
  배포 후 실제 화면에서 제출/재방문 시 카드 안 뜨는지 수동 확인

## 롤아웃

`main`에 직접, 작업 단위 커밋. 배포 후 curl로 `/api/review` 200/400
케이스 확인 + 실기기 또는 브라우저에서 카드 노출·제출·재방문 확인.
