# 인앱 피드백 리워드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 유저가 앱 안에서 10자 이상 짧은 피드백을 제출하면 20원을 즉시
1회(`anonKey` 기준) 받는 기능을 추가한다.

**Architecture:** 새 테이블 `app_reviews`(`anon_key` 기본키)로 중복 제출을
DB 레벨에서 막고, `/api/review` 핸들러가 `grant_reward()`(기존
`grant_click_reward`와 동일 패턴)로 즉시 리워드를 지급한다. 프론트는
`useFavorites`/`PushOptInCard`와 같은 로컬스토리지 기반 배너 카드 패턴을
그대로 따른다.

**Tech Stack:** Python 3.12, psycopg2-binary, Postgres(Neon), pytest,
React 19, TypeScript

**Spec:** `docs/superpowers/specs/2026-09-28-inapp-feedback-reward-design.md`

## Global Constraints

- 한 사람(`anonKey` 기준)은 평생 한 번만 리워드를 받는다 — DB PK로 강제,
  애플리케이션 레벨 상태 없음
- 제출 텍스트는 10자 미만이면 거부(400)
- 리워드 금액은 1회 20원 고정
- React 테스트 프레임워크 없음(확인됨) — 프론트 검증은 `npx tsc -b` +
  배포 후 수동 확인으로 한다
- 별도 브랜치 없이 `main`에 직접, 작업 단위로 커밋한다

---

### Task 1: DB — `app_reviews` 테이블 추가

**Files:**
- Modify: `init_db.py`
- Test: `tests/test_init_db.py`

**Interfaces:**
- Produces: `app_reviews(anon_key text primary key, body text not null,
  created_at timestamptz not null default now())` — Task 2가 이 테이블에
  insert한다

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_init_db.py`의 `test_init_db_is_idempotent` 함수 뒤에 추가:

```python
def test_init_db_creates_app_reviews_table(conn):
    init_db(conn)

    with conn.cursor() as cur:
        cur.execute(
            "select column_name from information_schema.columns where table_name = 'app_reviews'"
        )
        columns = {row[0] for row in cur.fetchall()}

    assert columns == {"anon_key", "body", "created_at"}
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python3 -m pytest tests/test_init_db.py::test_init_db_creates_app_reviews_table -v`
Expected: FAIL (`columns == set()` — 테이블이 없어서 빈 결과)

- [ ] **Step 3: DDL 추가**

`init_db.py`의 `DDL_STATEMENTS` 리스트 마지막에 추가:

```python
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
    """
    create table if not exists app_reviews (
        anon_key   text primary key,
        body       text not null,
        created_at timestamptz not null default now()
    )
    """,
]
```

(기존 4개 항목은 그대로 두고 새 DDL 하나만 리스트 끝에 추가하는 것 —
`init_db()` 함수 자체는 무변화.)

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_init_db.py -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add init_db.py tests/test_init_db.py
git commit -m "Add app_reviews table for in-app feedback reward feature"
```

---

### Task 2: 백엔드 — `submit_review()` + `/api/review` 핸들러

**Files:**
- Modify: `api/webhook.py`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: `grant_reward(anon_key, amount, promotion_code=None) -> dict`(기존)
- Produces: `submit_review(conn, anon_key: str, body: str) -> bool`,
  `POST /api/review` `{"anonKey": str, "text": str}` →
  `200 {"received": true}` 또는 `400 {"error": "..."}`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_webhook.py`의 `db_conn` 픽스처 다음에 추가(파일 하단):

```python
@pytest.fixture
def review_db_conn():
    if not os.environ.get("PRODUCTS_DB_DATABASE_URL"):
        pytest.skip("PRODUCTS_DB_DATABASE_URL not set - skipping live DB test")
    connection = psycopg2.connect(os.environ["PRODUCTS_DB_DATABASE_URL"])
    yield connection
    with connection.cursor() as cur:
        cur.execute("delete from app_reviews where anon_key like 'test-%'")
    connection.commit()
    connection.close()


def test_submit_review_inserts_once_and_ignores_repeat(review_db_conn):
    first = submit_review(review_db_conn, "test-anon-1", "이 앱 정말 좋아요 잘쓰고있어요")
    assert first is True

    with review_db_conn.cursor() as cur:
        cur.execute("select body from app_reviews where anon_key = %s", ("test-anon-1",))
        row = cur.fetchone()
    assert row == ("이 앱 정말 좋아요 잘쓰고있어요",)

    second = submit_review(review_db_conn, "test-anon-1", "다른 내용으로 다시 제출")
    assert second is False

    with review_db_conn.cursor() as cur:
        cur.execute("select count(*) from app_reviews where anon_key = %s", ("test-anon-1",))
        count = cur.fetchone()[0]
    assert count == 1
```

`from webhook import (...)` 블록에 `submit_review` 추가:

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
    submit_review,
)
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python3 -m pytest tests/test_webhook.py::test_submit_review_inserts_once_and_ignores_repeat -v`
Expected: FAIL (`ImportError: cannot import name 'submit_review'`)

- [ ] **Step 3: `submit_review` + 핸들러 + 라우트 구현**

`api/webhook.py`의 `fetch_products_by_ids` 함수 바로 뒤(`class handler`
정의 직전)에 추가:

```python
def submit_review(conn, anon_key: str, body: str) -> bool:
    """app_reviews에 (anon_key, body)를 넣는다. 이미 같은 anon_key로 제출한
    적이 있으면 조용히 무시(ON CONFLICT DO NOTHING) - anon_key가 PK라 이게
    "한 사람당 한 번"을 강제하는 전부다. 실제로 새로 삽입됐으면 True."""
    with conn.cursor() as cur:
        cur.execute(
            "insert into app_reviews (anon_key, body) values (%s, %s) on conflict (anon_key) do nothing",
            (anon_key, body),
        )
        inserted = cur.rowcount == 1
    conn.commit()
    return inserted
```

`do_POST`를 아래로 교체:

```python
    def do_POST(self):
        if self.path.startswith("/api/link"):
            self._handle_link_request()
        elif self.path.startswith("/api/test-reward"):
            self._handle_test_reward_request()
        elif self.path.startswith("/api/review"):
            self._handle_review_request()
        else:
            self._handle_order_event()
```

`_handle_test_reward_request` 메서드 바로 뒤에 새 핸들러 추가:

```python
    def _handle_review_request(self):
        db_url = os.environ.get(PRODUCTS_DB_URL_ENV)
        if not db_url:
            self._respond(500, {"error": "PRODUCTS_DB_DATABASE_URL not configured"}, cors=True)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(content_length) or b"{}")
            anon_key = str(body["anonKey"])
            text = str(body["text"])
        except (json.JSONDecodeError, KeyError, ValueError):
            self._respond(400, {"error": "anonKey and text are required"}, cors=True)
            return

        if len(text.strip()) < 10:
            self._respond(400, {"error": "text must be at least 10 characters"}, cors=True)
            return

        conn = psycopg2.connect(db_url)
        try:
            is_new = submit_review(conn, anon_key, text)
        finally:
            conn.close()

        if is_new:
            review_promotion_code = os.environ.get("REVIEW_PROMOTION_CODE")
            if review_promotion_code:
                try:
                    result = grant_reward(anon_key, 20, promotion_code=review_promotion_code)
                    print(f"[review-reward] anonKey={anon_key} result={result}")
                except Exception as e:
                    print(f"[review-reward] failed for anonKey={anon_key}: {e}")

        self._respond(200, {"received": True}, cors=True)
```

(`REVIEW_PROMOTION_CODE`가 아직 없어도(Task 4 전) 에러 없이 그냥 리워드
지급만 건너뛴다 — `grant_click_reward`가 `CLICK_PROMOTION_CODE` 없을 때
하는 것과 동일한 방어.)

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m pytest tests/test_webhook.py -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add api/webhook.py tests/test_webhook.py
git commit -m "Add /api/review endpoint for one-time in-app feedback reward"
```

---

### Task 3: 프론트 — 피드백 배너 카드 + `App.tsx` 연결

**Files:**
- Modify: `deep-discount-deals/src/trackedLink.ts`
- Create: `deep-discount-deals/src/useReviewPrompt.ts`
- Create: `deep-discount-deals/src/ReviewPromptCard.tsx`
- Modify: `deep-discount-deals/src/App.css`
- Modify: `deep-discount-deals/src/App.tsx`

**Interfaces:**
- Consumes: `getAnonKey(): Promise<string | null>`(`trackedLink.ts`에서
  export)
- Produces: `useReviewPrompt() -> { submitted: boolean; markSubmitted: () => void }`,
  `<ReviewPromptCard onSubmitted={() => void} />`

- [ ] **Step 1: `trackedLink.ts`의 `getAnonKey`를 export**

`deep-discount-deals/src/trackedLink.ts`에서 아래 줄을:

```ts
function getAnonKey(): Promise<string | null> {
```

아래로 교체(export 추가, 그 외 동일):

```ts
export function getAnonKey(): Promise<string | null> {
```

- [ ] **Step 2: `useReviewPrompt.ts` 작성**

`deep-discount-deals/src/useReviewPrompt.ts` 새로 생성:

```ts
import { useState } from 'react';

const STORAGE_KEY = 'hidden-deals:review-submitted';

function readSubmitted(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

function writeSubmitted() {
  try {
    localStorage.setItem(STORAGE_KEY, 'true');
  } catch {
    // 저장 공간이 없거나 접근이 막힌 환경 - 이번 세션엔 카드가 다시 떠도 무해함
  }
}

export function useReviewPrompt() {
  const [submitted, setSubmitted] = useState<boolean>(readSubmitted);

  const markSubmitted = () => {
    writeSubmitted();
    setSubmitted(true);
  };

  return { submitted, markSubmitted };
}
```

- [ ] **Step 3: `ReviewPromptCard.tsx` 작성**

`deep-discount-deals/src/ReviewPromptCard.tsx` 새로 생성:

```tsx
import { useState } from 'react';
import { getAnonKey } from './trackedLink';

const REVIEW_URL = 'https://shaerlink.vercel.app/api/review';
const MIN_LENGTH = 10;

export function ReviewPromptCard({ onSubmitted }: { onSubmitted: () => void }) {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(false);

  const handleSubmit = async () => {
    const anonKey = await getAnonKey();
    if (!anonKey) return;

    setSubmitting(true);
    setError(false);
    try {
      const res = await fetch(REVIEW_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anonKey, text }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      onSubmitted();
    } catch {
      setError(true);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="review-prompt-card">
      <span className="review-prompt-card__title">숨은특가 어때요? 한 줄 남기고 20원 받기</span>
      <textarea
        className="review-prompt-card__textarea"
        placeholder="어떤 점이 좋았는지, 아쉬운지 알려주세요 (10자 이상)"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {error && <span className="review-prompt-card__error">제출에 실패했어요. 다시 시도해주세요.</span>}
      <button
        type="button"
        className="review-prompt-card__submit"
        disabled={text.trim().length < MIN_LENGTH || submitting}
        onClick={handleSubmit}
      >
        {submitting ? '보내는 중...' : '보내고 20원 받기'}
      </button>
    </div>
  );
}
```

- [ ] **Step 4: CSS 추가**

`deep-discount-deals/src/App.css`의 `.push-opt-in-card__subtitle` 규칙
바로 뒤에 추가:

```css
.review-prompt-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: var(--space-3) var(--space-3) 0;
  padding: var(--space-3);
  border-radius: 16px;
  background: var(--color-bg);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.review-prompt-card__title {
  font-size: var(--font-size-body-small);
  font-weight: var(--font-weight-subtitle);
  color: var(--color-text-strong);
}

.review-prompt-card__textarea {
  min-height: 72px;
  padding: var(--space-2);
  border: 1px solid var(--color-bg-canvas);
  border-radius: 10px;
  background: var(--color-bg-canvas);
  font-size: var(--font-size-body-small);
  color: var(--color-text-strong);
  resize: none;
}

.review-prompt-card__textarea::placeholder {
  color: var(--color-text-subtle);
}

.review-prompt-card__error {
  font-size: var(--font-size-caption);
  color: var(--color-danger);
}

.review-prompt-card__submit {
  min-height: 44px;
  padding: 0 var(--space-4);
  border: none;
  border-radius: 10px;
  background: var(--brand-primary);
  color: var(--color-text-inverse);
  font-size: var(--font-size-body-small);
  font-weight: var(--font-weight-subtitle);
  cursor: pointer;
}

.review-prompt-card__submit:disabled {
  background: var(--color-bg-canvas);
  color: var(--color-text-disabled);
  cursor: default;
}
```

- [ ] **Step 5: `App.tsx`에 연결**

`import { PushOptInCard } from './PushOptInCard';` 바로 뒤에 추가:

```ts
import { ReviewPromptCard } from './ReviewPromptCard';
import { useReviewPrompt } from './useReviewPrompt';
```

`App()` 함수 안, `const { recentIds, recordView, removeView, clearAll } = useRecentlyViewed();`
바로 뒤에 추가:

```ts
  const { submitted: reviewSubmitted, markSubmitted: markReviewSubmitted } = useReviewPrompt();
```

`<PushOptInCard />` 바로 뒤에 추가:

```tsx
                {!reviewSubmitted && <ReviewPromptCard onSubmitted={markReviewSubmitted} />}
```

- [ ] **Step 6: 타입체크로 검증**

Run: `cd deep-discount-deals && npx tsc -b`
Expected: 에러 없이 종료

- [ ] **Step 7: 로컬 개발 서버로 수동 확인**

Run: `cd deep-discount-deals && npm run dev`(백그라운드)

브라우저로 열어서: 홈 화면에 피드백 카드가 뜨는지, 10자 미만이면 버튼이
비활성화되는지, 10자 이상 입력 후 제출하면 카드가 사라지는지(로컬
`/api/review` 호출은 배포 전이라 실패하겠지만 — 이 단계에서는 UI 동작만
확인, 실제 제출 성공은 Task 5 배포 후 확인). 확인 후 개발 서버 종료.

- [ ] **Step 8: 커밋**

```bash
git add deep-discount-deals/src/trackedLink.ts deep-discount-deals/src/useReviewPrompt.ts deep-discount-deals/src/ReviewPromptCard.tsx deep-discount-deals/src/App.css deep-discount-deals/src/App.tsx
git commit -m "Add in-app feedback prompt card wired to /api/review"
```

---

### Task 4: 콘솔 — 리워드 프로모션 생성 + 환경변수 설정

**Files:** 없음(콘솔 MCP 도구 + Vercel CLI)

- [ ] **Step 1: 예산 확인**

`promotion_money_balance`(workspaceId 61293)로 현재 실시간 사용 가능
잔액을 확인한다. **이 프로모션의 총 예산은 사용자에게 직접 확인하고
진행한다** — 실제 지갑 돈이 즉시 묶이는 결정이라 임의로 정하지 않는다.

- [ ] **Step 2: 프로모션 생성**

`promotion_create`(workspaceId 61293, miniAppId 71218)로 아래 payload
생성(⁠`totalBudget`은 Step 1에서 확인한 금액으로 교체):

```json
{
  "title": "피드백 남기고 포인트 받기",
  "totalBudget": <확인한 예산>,
  "maxSingleRewardAmount": 20,
  "dailyUserRewardLimitAmount": 20,
  "endTs": "2026-10-19T23:59:59Z",
  "enableBenefitTab": true,
  "benefitTabSpec": {
    "missionName": "한 줄 피드백 남기기",
    "rewardAmount": 20,
    "landingUrl": "intoss://hidden-deals",
    "allowVariableAmount": false
  },
  "isCurrencyExchange": false
}
```

응답의 `promotionCode`를 기록한다(다음 단계에서 씀).

- [ ] **Step 3: 승인 확인**

`promotion_get`으로 `approvalResult`가 `APPROVED`가 될 때까지 확인한다(즉시
되는 경우가 많으나, 안 되면 사용자에게 대기 시간을 안내하고 나중에 이어서
진행).

- [ ] **Step 4: 테스트 호출로 `isTested` 활성화**

로컬 `.env.local`(`deep-discount-deals/.env.local`)의
`VITE_LINK_API_TOKEN` 값으로 `/api/test-reward`를 직접 호출한다(오늘
세션에서 이미 확보한 실제 anonKey `BOty4XQqhR2x_T7w-udwaMo-ZR0` 재사용
가능 — 새 anonKey가 필요하면 `/ait:test-on-device`로 다시 뽑는다):

```bash
cd deep-discount-deals && TOKEN=$(grep "^VITE_LINK_API_TOKEN=" .env.local | cut -d= -f2-)
curl -sS -X POST https://shaerlink.vercel.app/api/test-reward \
  -H "Content-Type: application/json" \
  -H "x-internal-token: $TOKEN" \
  -d '{"promotionCode":"TEST_<Step 2의 promotionCode>","anonKey":"BOty4XQqhR2x_T7w-udwaMo-ZR0","amount":20}'
```

Expected: `{"resultType": "SUCCESS", ...}`. `promotion_get`으로
`isTested: true` 확인.

- [ ] **Step 5: `RUNNING` 전환**

`promotion_change_status`(status: `RUNNING`)로 전환.

- [ ] **Step 6: `REVIEW_PROMOTION_CODE` 환경변수 설정**

```bash
cd /Users/mac/claude/shaerlink
npx vercel env add REVIEW_PROMOTION_CODE production --no-sensitive
```

(값 입력 프롬프트에 Step 2의 `promotionCode`를 입력. `--no-sensitive`로
`PROMOTION_CODE`와 동일하게 나중에 다시 읽을 수 있는 Config 타입으로
저장한다.)

- [ ] **Step 7: 재배포**

```bash
npx vercel deploy --prod
```

(환경변수는 재배포해야 실행 중인 함수에 반영된다 — 오늘 세션에서
`PROMOTION_CODE` 교체 때도 동일하게 확인된 사실.)

---

### Task 5: 배포 후 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 400 케이스 확인**

Run: `curl -sS -w "\n%{http_code}\n" -X POST https://shaerlink.vercel.app/api/review -H "Content-Type: application/json" -d '{"anonKey":"test-verify","text":"짧음"}'`
Expected: `400`과 `{"error": "text must be at least 10 characters"}`

- [ ] **Step 2: 첫 제출 200 + 리워드 지급 확인**

Run: `curl -sS -w "\n%{http_code}\n" -X POST https://shaerlink.vercel.app/api/review -H "Content-Type: application/json" -d '{"anonKey":"test-verify","text":"이 정도면 충분히 긴 테스트 피드백입니다"}'`
Expected: `200`과 `{"received": true}`

Vercel 로그(`npx vercel logs shaerlink.vercel.app`)에서
`[review-reward] anonKey=test-verify result={'resultType': 'SUCCESS', ...}`
확인.

- [ ] **Step 3: 재제출 시 중복 리워드 없는지 확인**

Run: 같은 curl을 한 번 더 실행
Expected: `200`과 `{"received": true}`(에러 아님), 근데 로그에는
`[review-reward]` 줄이 **다시 안 찍혀야 함**(이미 제출한 `anon_key`라
`submit_review`가 `False` 반환 → 리워드 재호출 안 됨)

- [ ] **Step 4: 테스트 데이터 정리**

Run:
```bash
cd /Users/mac/claude/shaerlink
python3 -c "
import os, psycopg2
from sharelink_api import _load_dotenv
_load_dotenv()
conn = psycopg2.connect(os.environ['PRODUCTS_DB_DATABASE_URL'])
with conn.cursor() as cur:
    cur.execute(\"delete from app_reviews where anon_key = 'test-verify'\")
conn.commit()
conn.close()
"
```

- [ ] **Step 5: 실제 화면 확인**

토스 앱(또는 `npm run dev` 로컬)에서 홈 화면에 피드백 카드가 뜨는지,
10자 이상 입력 후 제출하면 실제로 사라지는지, 새로고침(또는 재방문) 후
다시 안 뜨는지 확인.
