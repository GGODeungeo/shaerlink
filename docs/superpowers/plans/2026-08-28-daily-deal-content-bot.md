# 하루특가 콘텐츠 생성 봇 (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Toss Sharelink "하루특가"(30일 최저가) 상품을 스크래핑해서 상품별로 쓰레드/틱톡/유튜브용 캡션을 생성하고, 이미지·링크·캡션을 사람이 바로 복사해 쓸 수 있는 폴더로 저장하는 CLI 파이프라인을 만든다.

**Architecture:** Playwright(저장된 브라우저 세션 재사용)로 상품 목록과 쉐어링크를 스크래핑 → `products.json`으로 저장 → Claude API로 상품별 캡션 3종 생성 → 이미지 다운로드 + 캡션/링크를 `output/YYYY-MM-DD/NNN-상품명/` 폴더 구조로 정리. 각 단계는 파일(JSON/이미지/마크다운)로만 통신해 나중에 스크래핑 단계를 공식 API로 교체해도 나머지는 그대로 재사용 가능.

**Tech Stack:** Python, Playwright(sync API), BeautifulSoup4, Anthropic Claude API(`claude-sonnet-5`), pytest. 외부 웹 프레임워크 없음.

**Spec:** `docs/superpowers/specs/2026-08-28-daily-deal-content-bot-design.md`

## Global Constraints

- Phase 1 범위만 구현한다: 스크래핑 + 캡션 생성 + 출력 패키징. SNS 자동 포스팅, Sharelink 공식 API 연동, 스케줄링(cron)은 이번 플랜에 포함하지 않는다.
- 로그인 세션이 만료된 것으로 감지되면 자동 재로그인을 시도하지 않고 즉시 에러로 중단한다.
- 상품이 0개 파싱되면 에러로 중단한다 (조용히 빈 출력 폴더를 만들지 않는다).
- Claude API 캡션 생성이 상품 하나에서 실패해도 그 상품만 건너뛰고 전체 파이프라인은 계속 진행한다.
- 의존성은 `playwright`, `beautifulsoup4`, `anthropic`, `pytest`만 사용한다. 웹 프레임워크나 ORM 등 이번 범위에 불필요한 패키지는 추가하지 않는다.
- 이 프로젝트는 공식 API가 없는 상태에서 본인 계정으로 로그인한 세션을 재사용해 자신의 화면을 읽는 개인용 스크립트다. 사이트 구조(HTML/클래스명)는 문서화되어 있지 않으므로, 아래 태스크 중 실제 페이지 대상 파싱/클릭 로직은 최초 실행 시 어긋날 수 있다 — 그 경우 systematic-debugging 스킬로 실제 캡처된 HTML/스크린샷을 보며 선택자를 맞춘다. 이것은 계획 실패가 아니라 예상된 반복이다.

---

### Task 1: 프로젝트 스캐폴딩 + 1회성 로그인 스크립트

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `pytest.ini`
- Create: `login.py`

**Interfaces:**
- Consumes: 없음 (최초 태스크)
- Produces: `browser-profile/` 디렉토리(로그인 세션 저장 위치, git에는 커밋 안 함) — 이후 모든 태스크가 이 디렉토리를 재사용

- [ ] **Step 1: 의존성 파일 작성**

`requirements.txt`:
```
playwright
beautifulsoup4
anthropic
pytest
```

- [ ] **Step 2: gitignore 작성**

`.gitignore`:
```
__pycache__/
*.pyc
output/
browser-profile/
.env
```

- [ ] **Step 3: pytest 설정 작성 (src 없이 루트에서 바로 import하기 위함)**

`pytest.ini`:
```ini
[pytest]
pythonpath = .
```

- [ ] **Step 4: 의존성 설치**

Run:
```bash
pip install -r requirements.txt
playwright install chromium
```

- [ ] **Step 5: 1회성 로그인 스크립트 작성**

`login.py`:
```python
import sys
from playwright.sync_api import sync_playwright

URL = "https://sharelink.toss.im"


def main():
    profile_dir = sys.argv[1] if len(sys.argv) > 1 else "browser-profile"
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = context.new_page()
        page.goto(URL)
        input("브라우저에서 로그인을 완료한 뒤 Enter를 눌러주세요...")
        context.close()
    print(f"세션이 {profile_dir}에 저장됐어요.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 로그인 세션 생성 (수동 검증)**

Run:
```bash
python login.py browser-profile
```

브라우저가 뜨면 실제 계정으로 로그인 후 터미널에서 Enter. 완료되면 확인:
```bash
ls browser-profile
```
Expected: 빈 디렉토리가 아니라 Chromium 프로필 파일들(Default 등)이 생성되어 있어야 함.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore pytest.ini login.py
git commit -m "feat: add project scaffolding and one-time login script"
```

---

### Task 2: 로그인 만료 감지 (`is_logged_out`)

**Files:**
- Create: `scrape.py`
- Test: `tests/test_scrape.py`

**Interfaces:**
- Consumes: 없음
- Produces: `is_logged_out(html: str) -> bool` — Task 4(스크래핑 오케스트레이션)가 사용

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_scrape.py`:
```python
from scrape import is_logged_out


def test_is_logged_out_true_when_login_page():
    html = "<html><body><h1>로그인</h1><button>로그인하기</button></body></html>"
    assert is_logged_out(html) is True


def test_is_logged_out_false_when_products_present():
    html = "<html><body><button>링크 발급</button></body></html>"
    assert is_logged_out(html) is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_scrape.py -v`
Expected: FAIL — `ImportError: cannot import name 'is_logged_out'`

- [ ] **Step 3: 최소 구현**

`scrape.py`:
```python
def is_logged_out(html: str) -> bool:
    return "링크 발급" not in html
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_scrape.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scrape.py tests/test_scrape.py
git commit -m "feat: detect expired login session from page html"
```

---

### Task 3: 상품 목록 파싱 (`parse_products`)

**Files:**
- Create: `scripts/capture_fixture.py`
- Create: `tests/fixtures/products_page.html` (실제 페이지에서 캡처)
- Modify: `scrape.py`
- Modify: `tests/test_scrape.py`

**Interfaces:**
- Consumes: Task 1의 `browser-profile/`
- Produces: `parse_products(html: str) -> list[dict]`, 각 dict는 `{"name": str, "price": int, "discountRate": int, "imageUrl": str}` — Task 4가 사용

- [ ] **Step 1: 실제 페이지 HTML 캡처용 스크립트 작성**

`scripts/capture_fixture.py`:
```python
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://sharelink.toss.im/links/recommended-products?priceFilters=MIN_PRICE_30D"


def main():
    profile_dir = sys.argv[1] if len(sys.argv) > 1 else "browser-profile"
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = context.new_page()
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        html = page.content()
        context.close()
    Path("tests/fixtures").mkdir(parents=True, exist_ok=True)
    Path("tests/fixtures/products_page.html").write_text(html, encoding="utf-8")
    print("saved tests/fixtures/products_page.html")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실제 페이지 캡처 실행**

Run:
```bash
python scripts/capture_fixture.py browser-profile
```
Expected: `tests/fixtures/products_page.html`가 생성되고, 파일을 열어보면 실제 하루특가 상품 목록이 들어있어야 함 (로그인 세션이 만료됐다면 Task 1 Step 6을 다시 실행).

- [ ] **Step 3: 캡처된 HTML 구조 확인 (코드 아님, 육안 확인)**

`tests/fixtures/products_page.html`을 열어서 상품명/가격/할인율/이미지가 어떤 태그·클래스로 감싸여 있는지 확인한다. "링크 발급" 텍스트를 가진 버튼을 기준으로 그 조상 요소를 따라 올라가며 상품 카드의 공통 컨테이너를 찾는다.

- [ ] **Step 4: 실패하는 테스트 작성 (실제 캡처 데이터 기준)**

`tests/test_scrape.py`에 추가:
```python
from pathlib import Path
from scrape import parse_products

FIXTURE = Path("tests/fixtures/products_page.html").read_text(encoding="utf-8")


def test_parse_products_returns_nonempty_list():
    products = parse_products(FIXTURE)
    assert len(products) > 0


def test_parse_products_fields_have_correct_types():
    products = parse_products(FIXTURE)
    first = products[0]
    assert isinstance(first["name"], str) and first["name"]
    assert isinstance(first["price"], int) and first["price"] > 0
    assert isinstance(first["discountRate"], int) and 0 <= first["discountRate"] <= 100
    assert first["imageUrl"].startswith("http")
```

- [ ] **Step 5: 테스트 실패 확인**

Run: `pytest tests/test_scrape.py -v`
Expected: FAIL — `parse_products`가 아직 없거나 빈 리스트 반환

- [ ] **Step 6: 구현**

`scrape.py`에 추가:
```python
import re
from bs4 import BeautifulSoup

PRICE_RE = re.compile(r"^[\d,]+원$")
DISCOUNT_RE = re.compile(r"(\d+)%\s*특가")


def _extract_price(card_text_lines: list[str]) -> int | None:
    for line in card_text_lines:
        line = line.strip()
        if "당" in line:
            continue
        if PRICE_RE.match(line):
            return int(line.replace(",", "").replace("원", ""))
    return None


def parse_products(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for button in soup.find_all(string=re.compile("링크 발급")):
        card = button.find_parent()
        while card is not None and card.find("img") is None:
            card = card.find_parent()
        if card is None:
            continue
        img = card.find("img")
        image_url = img.get("src", "") if img else ""
        name = img.get("alt", "").strip() if img else ""
        text_lines = [line for line in card.get_text("\n").split("\n") if line.strip()]
        price = _extract_price(text_lines)
        discount_match = DISCOUNT_RE.search(card.get_text(" "))
        discount_rate = int(discount_match.group(1)) if discount_match else 0
        if not name or price is None:
            continue
        products.append({
            "name": name,
            "price": price,
            "discountRate": discount_rate,
            "imageUrl": image_url,
        })
    return products
```

- [ ] **Step 7: 테스트 실행, 실패하면 systematic-debugging으로 조정**

Run: `pytest tests/test_scrace.py -v`

실제 페이지 구조가 위 가정(이미지 `alt`가 상품명, 링크 발급 버튼의 조상에 이미지 포함)과 다르면 실패한다. 이 경우 superpowers:systematic-debugging 스킬을 사용해 `tests/fixtures/products_page.html`을 직접 열어보며 실제 태그 구조에 맞게 `parse_products`를 조정한다. 통과할 때까지 반복.

Expected (최종): PASS

- [ ] **Step 8: Commit**

```bash
git add scrape.py scripts/capture_fixture.py tests/test_scrape.py tests/fixtures/products_page.html
git commit -m "feat: parse daily-deal products from sharelink html"
```

---

### Task 4: 스크래핑 오케스트레이션 (`run_scrape`, 쉐어링크 발급 포함)

**Files:**
- Modify: `scrape.py`

**Interfaces:**
- Consumes: `is_logged_out`, `parse_products` (Task 2, 3), `browser-profile/` (Task 1)
- Produces: `run_scrape(profile_dir: str, output_dir: Path) -> list[dict]` — 각 dict에 `shareLink: str` 키가 추가됨. `main.py`(Task 8)가 사용. 실행 결과로 `output_dir/products.json` 파일도 생성.

이 태스크는 실제 브라우저 클릭과 클립보드 동작에 의존해 자동화 테스트가 불가능하다 (스펙의 "전체 파이프라인은 실제 계정으로 1회 수동 실행 후 확인" 항목). 자동 테스트 대신 수동 검증 단계로 마무리한다.

- [ ] **Step 1: 구현**

`scrape.py`에 추가:
```python
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://sharelink.toss.im/links/recommended-products?priceFilters=MIN_PRICE_30D"

CLIPBOARD_HOOK = """
() => {
  window.__capturedLinks = [];
  const orig = navigator.clipboard.writeText.bind(navigator.clipboard);
  navigator.clipboard.writeText = (text) => {
    window.__capturedLinks.push(text);
    return orig(text);
  };
}
"""


def run_scrape(profile_dir: str, output_dir: Path) -> list[dict]:
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = context.new_page()
        page.add_init_script(CLIPBOARD_HOOK)
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        html = page.content()

        if is_logged_out(html):
            context.close()
            raise RuntimeError(
                "로그인 세션이 만료됐어요. `python login.py browser-profile`로 다시 로그인해주세요."
            )

        products = parse_products(html)
        if not products:
            context.close()
            raise RuntimeError("상품을 하나도 찾지 못했어요. 사이트 구조가 바뀌었을 수 있어요.")

        buttons = page.get_by_text("링크 발급")
        for i, product in enumerate(products):
            buttons.nth(i).click()
            page.wait_for_function(
                "(n) => window.__capturedLinks.length > n", arg=i
            )
            product["shareLink"] = page.evaluate("window.__capturedLinks.at(-1)")

        context.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "products.json").write_text(
        json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return products
```

- [ ] **Step 2: 수동 검증**

Run:
```bash
python -c "from pathlib import Path; from scrape import run_scrape; print(run_scrape('browser-profile', Path('output/manual-test')))"
```

Expected: 에러 없이 상품 리스트가 출력되고, `output/manual-test/products.json`이 생성됨. 각 상품에 `shareLink`가 `https://`로 시작하는 값으로 채워져 있는지 확인.

버튼 클릭 순서가 파싱 순서와 어긋나거나 클립보드 훅이 동작하지 않으면(사이트가 `writeText` 대신 다른 방식을 쓰는 경우) superpowers:systematic-debugging으로 실제 동작을 관찰하며 수정한다 — 예: Playwright Inspector(`PWDEBUG=1`)로 버튼 클릭 시 어떤 JS API가 호출되는지 확인.

- [ ] **Step 3: Commit**

```bash
git add scrape.py
git commit -m "feat: orchestrate scraping and share-link issuance"
```

---

### Task 5: 캡션 프롬프트 생성과 응답 파싱

**Files:**
- Create: `generate.py`
- Create: `tests/test_generate.py`

**Interfaces:**
- Consumes: `parse_products`가 만드는 product dict 형태 (`name`, `price`, `discountRate`)
- Produces: `build_prompt(product: dict) -> str`, `parse_caption_response(text: str) -> dict` (키: `threads`, `tiktok`, `youtube`) — Task 6이 사용

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_generate.py`:
```python
from generate import build_prompt, parse_caption_response


def test_build_prompt_includes_product_fields():
    product = {"name": "테스트 상품", "price": 12000, "discountRate": 61}
    prompt = build_prompt(product)
    assert "테스트 상품" in prompt
    assert "12000" in prompt
    assert "61" in prompt


def test_parse_caption_response_splits_three_sections():
    text = (
        "## threads\n"
        "쓰레드용 문구\n\n"
        "## tiktok\n"
        "틱톡용 문구 #특가\n\n"
        "## youtube\n"
        "유튜브용 설명\n"
    )
    result = parse_caption_response(text)
    assert result == {
        "threads": "쓰레드용 문구",
        "tiktok": "틱톡용 문구 #특가",
        "youtube": "유튜브용 설명",
    }
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_generate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'generate'`

- [ ] **Step 3: 구현**

`generate.py`:
```python
import re

PROMPT_TEMPLATE = """다음 상품에 대해 SNS 홍보 문구를 만들어줘.

상품명: {name}
가격: {price}원
할인율: {discount}%

아래 형식을 반드시 그대로 지켜서 출력해:

## threads
(캐주얼한 말투, 2~3문장, 이모지 최소화)

## tiktok
(짧고 후킹되는 한 문장 + 해시태그 2~3개)

## youtube
(설명형, 상품 특징과 할인 포인트를 3~4문장으로)
"""

SECTION_RE = re.compile(r"^##\s*(threads|tiktok|youtube)\s*$", re.MULTILINE)


def build_prompt(product: dict) -> str:
    return PROMPT_TEMPLATE.format(
        name=product["name"], price=product["price"], discount=product["discountRate"]
    )


def parse_caption_response(text: str) -> dict:
    parts = SECTION_RE.split(text)
    result = {}
    for i in range(1, len(parts), 2):
        platform = parts[i].strip().lower()
        content = parts[i + 1].strip()
        result[platform] = content
    return result
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_generate.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add generate.py tests/test_generate.py
git commit -m "feat: build caption prompt and parse three-platform response"
```

---

### Task 6: Claude API 호출과 실패 격리 (`generate_captions`, `generate_all_captions`)

**Files:**
- Modify: `generate.py`
- Modify: `tests/test_generate.py`

**Interfaces:**
- Consumes: `build_prompt`, `parse_caption_response` (Task 5)
- Produces: `generate_captions(product: dict) -> dict`, `generate_all_captions(products: list[dict]) -> list[dict]` (각 product에 `captions` 키 추가, 실패 시 `None`) — `main.py`(Task 8)가 사용

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_generate.py`에 추가:
```python
import sys
from types import SimpleNamespace
import generate
from generate import generate_captions, generate_all_captions


class FakeClient:
    def __init__(self, text):
        self._text = text

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text=self._text)])


def test_generate_captions_uses_client_and_parses_response(monkeypatch):
    fake_text = "## threads\nA\n\n## tiktok\nB\n\n## youtube\nC\n"
    monkeypatch.setattr(generate, "get_client", lambda: FakeClient(fake_text))
    product = {"name": "테스트", "price": 1000, "discountRate": 10}
    result = generate_captions(product)
    assert result == {"threads": "A", "tiktok": "B", "youtube": "C"}


def test_generate_all_captions_skips_failed_product(monkeypatch, capsys):
    calls = {"n": 0}

    def fake_generate_captions(product):
        calls["n"] += 1
        if product["name"] == "실패상품":
            raise RuntimeError("api down")
        return {"threads": "ok", "tiktok": "ok", "youtube": "ok"}

    monkeypatch.setattr(generate, "generate_captions", fake_generate_captions)
    products = [
        {"name": "실패상품", "price": 1, "discountRate": 1},
        {"name": "정상상품", "price": 2, "discountRate": 2},
    ]
    result = generate_all_captions(products)
    assert result[0]["captions"] is None
    assert result[1]["captions"] == {"threads": "ok", "tiktok": "ok", "youtube": "ok"}
    assert calls["n"] == 2
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_generate.py -v`
Expected: FAIL — `get_client`/`generate_captions`/`generate_all_captions`가 아직 없음

- [ ] **Step 3: 구현**

`generate.py`에 추가:
```python
import os
import sys
import anthropic

MODEL = "claude-sonnet-5"
_client = None


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def generate_captions(product: dict) -> dict:
    prompt = build_prompt(product)
    response = get_client().messages.create(
        model=MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_caption_response(response.content[0].text)


def generate_all_captions(products: list[dict]) -> list[dict]:
    for product in products:
        try:
            product["captions"] = generate_captions(product)
        except Exception as e:
            print(f"캡션 생성 실패: {product['name']} ({e})", file=sys.stderr)
            product["captions"] = None
    return products
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_generate.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add generate.py tests/test_generate.py
git commit -m "feat: call claude api for captions with per-product failure isolation"
```

---

### Task 7: 출력 폴더 도우미 함수 (`slugify`, `download_image`, `write_captions_md`)

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

**Interfaces:**
- Consumes: 없음 (순수 함수 + 파일 I/O)
- Produces: `slugify(name: str) -> str`, `download_image(url: str, dest: Path) -> bool`, `write_captions_md(dest: Path, captions: dict | None) -> None` — Task 8의 `main()`이 사용

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_main.py`:
```python
from pathlib import Path
import main


def test_slugify_replaces_spaces_and_truncates():
    assert main.slugify("Cool Product Name") == "Cool-Product-Name"
    assert main.slugify("아토몽드 키즈앤맘") == "아토몽드-키즈앤맘"


def test_write_captions_md_with_captions(tmp_path):
    dest = tmp_path / "captions.md"
    main.write_captions_md(dest, {"threads": "A", "tiktok": "B", "youtube": "C"})
    content = dest.read_text(encoding="utf-8")
    assert "## threads" in content and "A" in content
    assert "## youtube" in content and "C" in content


def test_write_captions_md_without_captions(tmp_path):
    dest = tmp_path / "captions.md"
    main.write_captions_md(dest, None)
    assert "실패" in dest.read_text(encoding="utf-8")


def test_download_image_success(tmp_path, monkeypatch):
    def fake_urlretrieve(url, dest):
        Path(dest).write_bytes(b"fake")

    monkeypatch.setattr(main.urllib.request, "urlretrieve", fake_urlretrieve)
    dest = tmp_path / "image.jpg"
    assert main.download_image("http://example.com/a.jpg", dest) is True
    assert dest.exists()


def test_download_image_failure(tmp_path, monkeypatch):
    def fake_urlretrieve(url, dest):
        raise OSError("boom")

    monkeypatch.setattr(main.urllib.request, "urlretrieve", fake_urlretrieve)
    dest = tmp_path / "image.jpg"
    assert main.download_image("http://example.com/a.jpg", dest) is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — `main.py`가 아직 없음

- [ ] **Step 3: 구현**

`main.py`:
```python
import re
import sys
import urllib.request
from pathlib import Path


def slugify(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned[:30] or "product"


def download_image(url: str, dest: Path) -> bool:
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        print(f"이미지 다운로드 실패: {url} ({e})", file=sys.stderr)
        return False


def write_captions_md(dest: Path, captions: dict | None) -> None:
    if captions is None:
        dest.write_text("(캡션 생성 실패)\n", encoding="utf-8")
        return
    lines = []
    for platform in ("threads", "tiktok", "youtube"):
        lines.append(f"## {platform}\n")
        lines.append(captions.get(platform, "").strip() + "\n\n")
    dest.write_text("".join(lines), encoding="utf-8")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_main.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add output folder helpers for slug, image download, captions file"
```

---

### Task 8: 전체 파이프라인 조립 (`main()`) + 수동 E2E 검증

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `run_scrape` (Task 4), `generate_all_captions` (Task 6), `slugify`/`download_image`/`write_captions_md` (Task 7)
- Produces: 실행 가능한 CLI (`python main.py`) — 이 플랜의 최종 산출물

- [ ] **Step 1: 구현**

`main.py`에 추가:
```python
import os
from datetime import date
from scrape import run_scrape
from generate import generate_all_captions

PROFILE_DIR = os.environ.get("BROWSER_PROFILE_DIR", "browser-profile")


def main():
    today = date.today().isoformat()
    output_dir = Path("output") / today

    products = run_scrape(PROFILE_DIR, output_dir)
    products = generate_all_captions(products)

    for i, product in enumerate(products, start=1):
        folder = output_dir / f"{i:03d}-{slugify(product['name'])}"
        folder.mkdir(parents=True, exist_ok=True)
        download_image(product["imageUrl"], folder / "image.jpg")
        (folder / "link.txt").write_text(product["shareLink"] + "\n", encoding="utf-8")
        write_captions_md(folder / "captions.md", product.get("captions"))

    print(f"완료: {output_dir} ({len(products)}개 상품)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 기존 테스트 전체가 여전히 통과하는지 확인**

Run: `pytest -v`
Expected: 이전 태스크에서 작성한 테스트 전부 PASS (import 순서/순환 참조 문제 없는지 확인)

- [ ] **Step 3: 수동 E2E 실행**

Run:
```bash
export ANTHROPIC_API_KEY=...  # 실제 키
python main.py
```

확인할 것:
- 에러 없이 끝까지 실행되는지
- `output/<오늘날짜>/` 아래에 그날 하루특가 상품 개수만큼 폴더가 생성됐는지 (Sharelink 사이트의 하루특가 섹션에서 눈으로 개수 대조)
- 폴더마다 `image.jpg`(정상 이미지), `link.txt`(`https://`로 시작하는 쉐어링크), `captions.md`(threads/tiktok/youtube 3섹션) 존재하는지
- 캡션 내용이 실제 상품명/가격과 맞는 자연스러운 문구인지 1~2개 폴더 직접 열어서 확인

문제가 있으면(폴더 개수 불일치, 깨진 캡션, 로그인 만료 처리 안 됨 등) superpowers:systematic-debugging으로 원인을 좁혀 수정하고 관련 태스크의 테스트를 보강한 뒤 다시 실행한다.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: wire scrape, caption generation, and output packaging into main pipeline"
```
