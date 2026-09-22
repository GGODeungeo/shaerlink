import { Review } from '@apps-in-toss/web-framework';

const STORAGE_KEY = 'hidden-deals:review-requested';

function alreadyAsked(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

function markAsked() {
  try {
    localStorage.setItem(STORAGE_KEY, 'true');
  } catch {
    // 저장 공간이 없거나 접근이 막힌 환경 - 이번 세션에는 다시 물어봐도 무해함
  }
}

/** Asks for a review once per device, right after the user hits a real
 * "core task succeeded" moment (here: tapping through to buy). Never blocks
 * or gates that flow - the SDK may not show anything at all, and a purchase
 * must proceed either way. */
export async function requestReviewOnce(): Promise<void> {
  if (alreadyAsked()) return;
  if (!Review.request.isSupported()) return;

  markAsked();
  try {
    await Review.request();
  } catch {
    // 미지원 버전 등 - 이미 asked 처리했으니 다음에 다시 시도하지 않음
  }
}
