import re
from typing import Optional
from bs4 import BeautifulSoup

PRICE_RE = re.compile(r"^[\d,]+원$")
DISCOUNT_RE = re.compile(r"(\d+)%\s*특가")


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
