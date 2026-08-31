import json
import re
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

PRICE_RE = re.compile(r"^[\d,]+원$")
DISCOUNT_RE = re.compile(r"(\d+)%\s*특가")

URL = "https://sharelink.toss.im/links/recommended-products?priceFilters=MIN_PRICE_30D"
LINK_ISSUE_URL_PART = "sharelink/link/issue"


def is_logged_out(html: str) -> bool:
    return "로그인" in html and "링크 발급" not in html


def _extract_price(card_text_lines: list[str]) -> Optional[int]:
    prices = []
    for line in card_text_lines:
        line = line.strip()
        if "당" in line:
            continue
        if PRICE_RE.match(line):
            prices.append(int(line.replace(",", "").replace("원", "")))
    return min(prices) if prices else None


def _extract_name(card) -> str:
    # The real site renders the product name in a dedicated text component
    # rather than the image's alt attribute (which is absent entirely).
    # Fall back to alt text for simpler hand-written test fixtures.
    name_el = card.find(attrs={"data-sentry-component": "LineClampTxt"})
    if name_el is not None:
        return name_el.get_text(strip=True)
    img = card.find("img")
    return img.get("alt", "").strip() if img else ""


def parse_products(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for idx, button in enumerate(soup.find_all(string=re.compile("링크 발급"))):
        card = button.find_parent()
        while card is not None and card.find("img") is None:
            card = card.find_parent()
        if card is None:
            continue
        img = card.find("img")
        image_url = img.get("src", "") if img else ""
        name = _extract_name(card)
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
            "_buttonIndex": idx,
        })
    return products


def run_scrape(profile_dir: str, output_dir: Path) -> list[dict]:
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = context.new_page()
        page.goto(URL)
        page.wait_for_load_state("networkidle")

        previous_height = 0
        for _ in range(20):  # hard cap so a real infinite-scroll page can't loop forever
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
