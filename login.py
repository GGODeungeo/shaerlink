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
