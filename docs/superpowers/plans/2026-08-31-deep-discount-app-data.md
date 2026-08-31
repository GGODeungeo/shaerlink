# 반값특가 앱데이터 파이프라인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 스크래퍼가 수집한 상품 중 할인율 50% 이상만 걸러서, 앱인토스 미니앱이 읽을 `app-data/products.json`을 생성하는 스크립트를 만든다.

**Architecture:** `scrape.py`의 `run_scrape`에 선택적 `filter_fn` 파라미터를 추가해 링크 발급 전에 필터링하고, 새 `build_app_data.py`가 이를 호출해 슬림한 JSON으로 저장한다. 이 플랜은 데이터 파이프라인만 다룬다 — 미니앱 프론트엔드(스캐폴딩, 화면 구현)는 별도로 진행한다 (이 계획의 범위 밖).

**Tech Stack:** Python (기존과 동일, 새 의존성 없음)

**Spec:** `docs/superpowers/specs/2026-08-31-deep-discount-miniapp-design.md`

## Global Constraints

- `run_scrape`에 `filter_fn` 파라미터를 추가하되 기본값 `None`으로 두어, 기존 `main.py`(Phase 1) 호출은 동작이 전혀 바뀌지 않아야 한다.
- 필터 기준(할인율)은 50% 이상 (`discountRate >= 50`).
- `app-data/products.json`은 상품마다 `name`, `price`, `discountRate`, `imageUrl`, `shareLink` 5개 필드만 포함하고, 할인율 내림차순으로 정렬한다.
- 필터 후 상품이 0개면 조용히 빈 파일을 만들지 않고 에러로 중단한다 (기존 `run_scrape`가 이미 "상품 0개" 에러를 던지므로, 필터 적용 시점을 그 에러 검사보다 뒤로 두어 자연히 같은 경로를 타게 한다).
- 의존성 추가 없음 (표준 라이브러리 + 기존 playwright/beautifulsoup4만 사용).
- `main.py`는 이 플랜에서 건드리지 않는다.

---

### Task 1: `run_scrape`에 `filter_fn` 파라미터 추가

**Files:**
- Modify: `scrape.py`

**Interfaces:**
- Consumes: 없음 (기존 `parse_products`, `is_logged_out` 그대로 사용)
- Produces: `run_scrape(profile_dir: str, output_dir: Path, filter_fn: Optional[Callable[[list[dict]], list[dict]]] = None) -> list[dict]` — Task 2의 `build_app_data.py`가 사용

이 태스크는 실제 브라우저와 로그인 세션이 필요해 자동 테스트가 불가능하다 (기존 `run_scrape`와 동일한 제약, 스펙의 테스트 섹션 참고). `filter_fn=None`일 때 기존 동작이 그대로인지는 코드 리뷰와 기존 `main.py` 재실행으로 확인한다.

- [ ] **Step 1: 구현**

`scrape.py`에서 `run_scrape` 시그니처와 본문을 다음과 같이 수정한다:

```python
from typing import Callable, Optional

def run_scrape(
    profile_dir: str,
    output_dir: Path,
    filter_fn: Optional[Callable[[list], list]] = None,
) -> list[dict]:
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = context.new_page()
        page.goto(URL)
        page.wait_for_load_state("networkidle")

        previous_height = 0
        for _ in range(20):
            page.keyboard.press("End")
            page.wait_for_timeout(500)
            current_height = page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                break
            previous_height = current_height

        html = page.content()

        if is_logged_out(html):
            context.close()
            raise RuntimeError(
                "로그인 세션이 만료됐거나 페이지가 제대로 로드되지 않았어요. "
                "`python login.py browser-profile`로 다시 로그인해보고, 그래도 안 되면 "
                "사이트 구조가 바뀌었는지 확인해주세요."
            )

        products = parse_products(html)
        if not products:
            context.close()
            raise RuntimeError("상품을 하나도 찾지 못했어요. 사이트 구조가 바뀌었을 수 있어요.")

        if filter_fn is not None:
            products = filter_fn(products)
            if not products:
                context.close()
                raise RuntimeError("필터링 후 남은 상품이 없어요.")

        buttons = page.get_by_text("링크 발급")
        for product in products:
            with page.expect_response(lambda r: LINK_ISSUE_URL_PART in r.url) as resp_info:
                buttons.nth(product["_buttonIndex"]).click()
            data = resp_info.value.json()
            product["shareLink"] = data["success"]["shortUrl"]
            del product["_buttonIndex"]

        context.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "products.json").write_text(
        json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return products
```

(이 태스크가 바꾸는 부분은 함수 시그니처에 `filter_fn` 파라미터 추가 + `if filter_fn is not None:` 블록 삽입뿐이다. 나머지는 기존 코드 그대로.)

- [ ] **Step 2: 기존 테스트 전체 실행 (회귀 확인)**

Run: `pytest -v`
Expected: 기존 테스트 전부 PASS — `run_scrape` 자체는 테스트 대상이 아니었으므로 개수 변화 없음.

- [ ] **Step 3: `python -c "import scrape"` 로 문법 오류 없는지 확인**

Run: `python3 -c "import scrape"`
Expected: 에러 없이 종료.

- [ ] **Step 4: Commit**

```bash
git add scrape.py
git commit -m "feat: add optional filter_fn to run_scrape for pre-link-issuance filtering"
```

---

### Task 2: `build_app_data.py` 작성 (필터/슬림화 로직 TDD)

**Files:**
- Create: `build_app_data.py`
- Create: `tests/test_build_app_data.py`

**Interfaces:**
- Consumes: `run_scrape(profile_dir, output_dir, filter_fn)` (Task 1)
- Produces: `is_deep_discount(product: dict) -> bool`, `to_app_data(products: list[dict]) -> list[dict]` — 둘 다 순수 함수, 단위 테스트 가능. `main()`은 이 둘과 `run_scrape`를 엮는 진입점.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_build_app_data.py`:
```python
from build_app_data import is_deep_discount, to_app_data


def test_is_deep_discount_threshold():
    assert is_deep_discount({"discountRate": 49}) is False
    assert is_deep_discount({"discountRate": 50}) is True
    assert is_deep_discount({"discountRate": 90}) is True


def test_to_app_data_slims_fields_and_sorts_by_discount_desc():
    products = [
        {
            "name": "낮은할인",
            "price": 1000,
            "discountRate": 55,
            "imageUrl": "https://a",
            "shareLink": "https://toss.im/a",
            "_extraFieldFromScraping": "무시돼야 함",
        },
        {
            "name": "높은할인",
            "price": 2000,
            "discountRate": 80,
            "imageUrl": "https://b",
            "shareLink": "https://toss.im/b",
        },
    ]
    result = to_app_data(products)
    assert result == [
        {
            "name": "높은할인",
            "price": 2000,
            "discountRate": 80,
            "imageUrl": "https://b",
            "shareLink": "https://toss.im/b",
        },
        {
            "name": "낮은할인",
            "price": 1000,
            "discountRate": 55,
            "imageUrl": "https://a",
            "shareLink": "https://toss.im/a",
        },
    ]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_build_app_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_app_data'`

- [ ] **Step 3: 구현**

`build_app_data.py`:
```python
import json
import sys
from datetime import date
from pathlib import Path

from scrape import run_scrape

MIN_DISCOUNT = 50
PROFILE_DIR = "browser-profile"
APP_DATA_PATH = Path("app-data/products.json")


def is_deep_discount(product: dict) -> bool:
    return product["discountRate"] >= MIN_DISCOUNT


def to_app_data(products: list) -> list:
    slim = [
        {
            "name": p["name"],
            "price": p["price"],
            "discountRate": p["discountRate"],
            "imageUrl": p["imageUrl"],
            "shareLink": p["shareLink"],
        }
        for p in products
    ]
    slim.sort(key=lambda p: -p["discountRate"])
    return slim


def main():
    today = date.today().isoformat()
    output_dir = Path("output") / today

    try:
        products = run_scrape(
            PROFILE_DIR, output_dir, filter_fn=lambda ps: [p for p in ps if is_deep_discount(p)]
        )
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    data = to_app_data(products)
    APP_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {APP_DATA_PATH} ({len(data)}개 상품)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_build_app_data.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 전체 테스트 스위트 회귀 확인**

Run: `pytest -v`
Expected: 기존 테스트 + 새 테스트 2개 전부 PASS

- [ ] **Step 6: Commit**

```bash
git add build_app_data.py tests/test_build_app_data.py
git commit -m "feat: add build_app_data script producing filtered, slimmed product json"
```

---

### Task 3: 수동 라이브 실행 검증

**Files:** 없음 (검증만)

- [ ] **Step 1: 실제 실행**

Run:
```bash
python3 build_app_data.py
```

확인할 것:
- 에러 없이 끝까지 실행되는지
- `app-data/products.json`이 생성됐는지, 각 항목이 정확히 5개 필드(`name`, `price`, `discountRate`, `imageUrl`, `shareLink`)만 가지는지
- `discountRate`가 전부 50 이상인지, 내림차순 정렬인지
- 기존 `python3 main.py`(Phase 1)를 다시 돌려서 여전히 정상 동작하는지 (회귀 확인 — `filter_fn=None` 경로)

문제가 있으면 systematic-debugging으로 원인을 좁혀 수정한다.

- [ ] **Step 2: `.gitignore`에 `app-data/`를 추가할지 결정**

`app-data/products.json`은 나중에 GitHub에 공개로 올릴 파일이므로 gitignore하지 않는다 — 이미 `.gitignore`에 해당 패턴이 없는지 확인만 하고, 있다면 제거한다.

Run: `grep -n "app-data" .gitignore`
Expected: 매치 없음 (아무 것도 출력 안 됨)
