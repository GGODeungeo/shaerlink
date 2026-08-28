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
