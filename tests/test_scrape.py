from pathlib import Path
from scrape import is_logged_out, parse_products

FIXTURE = Path("tests/fixtures/products_page.html").read_text(encoding="utf-8")


def test_is_logged_out_true_when_login_page():
    html = "<html><body><h1>로그인</h1><button>로그인하기</button></body></html>"
    assert is_logged_out(html) is True


def test_is_logged_out_false_when_products_present():
    html = "<html><body><button>링크 발급</button></body></html>"
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
