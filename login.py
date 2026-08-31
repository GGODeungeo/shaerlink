import sys
from playwright.sync_api import sync_playwright
from scrape import is_logged_out, URL

POLL_MS = 3000
TIMEOUT_MS = 300000  # 5 minutes


def main():
    profile_dir = sys.argv[1] if len(sys.argv) > 1 else "browser-profile"
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = context.new_page()
        page.goto(URL)
        print("브라우저에서 로그인을 완료해주세요. 로그인을 감지하면 자동으로 세션을 저장하고 종료해요 (최대 5분 대기).")

        waited = 0
        while waited < TIMEOUT_MS:
            page.wait_for_timeout(POLL_MS)
            waited += POLL_MS
            if not is_logged_out(page.content()):
                print("로그인이 확인됐어요. 세션을 저장할게요.")
                break
        else:
            print("5분 안에 로그인이 확인되지 않았어요. 지금 상태로 세션을 저장할게요.")

        context.close()
    print(f"세션이 {profile_dir}에 저장됐어요.")


if __name__ == "__main__":
    main()
