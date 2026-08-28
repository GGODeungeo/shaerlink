def is_logged_out(html: str) -> bool:
    return "링크 발급" not in html
