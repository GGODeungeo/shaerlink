import json
import re
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

PRICE_RE = re.compile(r"^[\d,]+원$")
DISCOUNT_RE = re.compile(r"(\d+)%\s*특가")

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


def is_logged_out(html: str) -> bool:
    return "링크 발급" not in html


def _extract_price(card_text_lines: list[str]) -> Optional[int]:
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
