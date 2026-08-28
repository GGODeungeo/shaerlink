import re
from pathlib import Path
from scrape import is_logged_out, parse_products

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "products_page.html"
FIXTURE = FIXTURE_PATH.read_text(encoding="utf-8")


def test_is_logged_out_true_when_login_page():
    html = "<html><body><h1>로그인</h1><button>로그인하기</button></body></html>"
    assert is_logged_out(html) is True


def test_is_logged_out_false_when_products_present():
    html = "<html><body><button>링크 발급</button></body></html>"
    assert is_logged_out(html) is False


def test_is_logged_out_false_when_page_structure_changed_without_login_signal():
    # No "로그인" text and no "링크 발급" text - e.g. the SPA hasn't finished
    # rendering, or the site renamed the button. This must NOT be
    # misdiagnosed as "session expired" - it should fall through to the
    # separate "zero products found" error path instead.
    html = "<html><body><div id=\"app\"></div></body></html>"
    assert is_logged_out(html) is False


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


def test_parse_products_skips_invalid_card_and_keeps_correct_button_indices():
    # The fixture has 5 "링크 발급" occurrences total; the middle one (button
    # index 2) belongs to a sold-out card with no parseable price and must
    # be skipped by parse_products. Naively pairing surviving products with
    # buttons by their position *within the returned list* would then
    # misalign every product after the skipped one with the wrong button/
    # share link. Each surviving product must instead carry its ORIGINAL
    # position among ALL "링크 발급" occurrences on the page.
    total_buttons = len(re.findall("링크 발급", FIXTURE))
    assert total_buttons == 5

    products = parse_products(FIXTURE)
    assert len(products) == 4
    assert all("품절" not in p["name"] for p in products)
    assert [p["_buttonIndex"] for p in products] == [0, 1, 3, 4]


def test_extract_price_picks_minimum_when_multiple_price_lines():
    # The first card's price block lists a struck-through original price
    # before the discounted price, in that DOM order. The parser must pick
    # the minimum (discounted) price, not the first matching line.
    products = parse_products(FIXTURE)
    atomond = next(p for p in products if "아토몽드" in p["name"])
    assert atomond["price"] == 27920
