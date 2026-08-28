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


SKIP_CASE_HTML = """
<html><body>
{}
</body></html>
""".format("".join(
    f'''<div class="card">
          <img src="https://example.com/{i}.jpg" />
          <span data-sentry-component="LineClampTxt">상품{i}</span>
          {'<p>품절</p>' if i == 2 else f'<p>{(i + 1) * 1000}원</p>'}
          <button>링크 발급</button>
        </div>'''
    for i in range(5)
))


def test_parse_products_skips_invalid_card_and_keeps_correct_button_indices():
    # Card index 2 (of 5) has no parseable price ("품절") and must be
    # skipped by parse_products. Naively pairing surviving products with
    # buttons by their position *within the returned list* would then
    # misalign every product after the skipped one with the wrong button/
    # share link. Each surviving product must instead carry its ORIGINAL
    # position among ALL "링크 발급" occurrences on the page.
    total_buttons = len(re.findall("링크 발급", SKIP_CASE_HTML))
    assert total_buttons == 5

    products = parse_products(SKIP_CASE_HTML)
    assert len(products) == 4
    assert all("상품2" != p["name"] for p in products)
    assert [p["_buttonIndex"] for p in products] == [0, 1, 3, 4]


MULTI_PRICE_HTML = """
<html><body>
  <div class="card">
    <img src="https://example.com/a.jpg" />
    <span data-sentry-component="LineClampTxt">테스트 상품</span>
    <p>35,900원</p>
    <p>27,920원</p>
    <button>링크 발급</button>
  </div>
</body></html>
"""


def test_extract_price_picks_minimum_when_multiple_price_lines():
    # A struck-through original price rendered before the discounted price,
    # in that DOM order. The parser must pick the minimum (discounted)
    # price, not the first matching line.
    products = parse_products(MULTI_PRICE_HTML)
    assert products[0]["price"] == 27920


def test_parse_products_name_uses_line_clamp_text_not_missing_alt():
    # The real site's <img> has no alt attribute at all - the name lives in
    # a separate LineClampTxt component. This is a regression test for that.
    html = """
    <html><body>
      <div class="card">
        <img src="https://example.com/a.jpg" />
        <span data-sentry-component="LineClampTxt">실제 상품명</span>
        <p>9,900원</p>
        <button>링크 발급</button>
      </div>
    </body></html>
    """
    products = parse_products(html)
    assert products[0]["name"] == "실제 상품명"
