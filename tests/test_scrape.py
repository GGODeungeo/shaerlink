from scrape import is_logged_out


def test_is_logged_out_true_when_login_page():
    html = "<html><body><h1>로그인</h1><button>로그인하기</button></body></html>"
    assert is_logged_out(html) is True


def test_is_logged_out_false_when_products_present():
    html = "<html><body><button>링크 발급</button></body></html>"
    assert is_logged_out(html) is False
