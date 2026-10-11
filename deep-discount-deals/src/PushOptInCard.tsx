import { useEffect, useState } from 'react';
import { Analytics, Notification } from '@apps-in-toss/web-framework';
import { useLockBodyScroll } from './useLockBodyScroll';
import { getAnonKey } from './trackedLink';

const TEMPLATE_CODE = 'hidden-deals-DAILY_DEAL_PUSH';
const STORAGE_KEY = 'hidden-deals:push-agreement-asked';
const PUSH_REWARD_URL = 'https://shaerlink.vercel.app/api/push-reward';
const VISITS_KEY = 'hidden-deals:visit-count';
const OPEN_DELAY_MS = 800;

/** 이번 진입을 세고 누적 방문 수를 돌려준다. 저장이 막힌 환경이면 0 -
 * 그 경우 묻지 않는다(첫 방문으로 취급). */
function countVisit(): number {
  try {
    const visits = Number(localStorage.getItem(VISITS_KEY) ?? '0') + 1;
    localStorage.setItem(VISITS_KEY, String(visits));
    return visits;
  } catch {
    return 0;
  }
}

// 모듈 로드 = 앱 진입 1회. effect 안에서 세면 StrictMode 이중 실행에 두 번 센다.
const VISITS = countVisit();

function alreadyAsked(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function markAsked() {
  try {
    localStorage.setItem(STORAGE_KEY, '1');
  } catch {
    // 저장 공간이 없거나 접근이 막힌 환경 - 다음에 다시 물어봐도 무해함
  }
}

/** Best-effort reward grant for a brand-new push agreement - never throws,
 * doesn't block the opt-in UI (same spirit as trackedLink's click reward). */
async function grantPushReward() {
  try {
    const anonKey = await getAnonKey();
    if (!anonKey) return;
    await fetch(PUSH_REWARD_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anonKey }),
    });
  } catch {
    // best-effort - a failed grant must not break the opt-in flow
  }
}

/** Asks once, shortly after the user starts browsing, whether to receive deal
 * push notifications - a small confirm dialog instead of a persistent
 * home-screen card. Whatever the user picks, it's marked asked and never
 * shown again.
 *
 * Never on the first visit: review rejected three versions for a sheet
 * appearing right after entry - any scroll-based trigger fires within
 * seconds when someone opens the app and starts scrolling. From the second
 * visit on, it waits for a real gesture (touchmove/wheel - 'scroll' also
 * fires from programmatic scrollTo and layout shifts) past one screen. */
export function PushOptInPrompt() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (VISITS < 2 || alreadyAsked() || !Notification.requestAgreement.isSupported()) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const gestures = ['touchmove', 'wheel'] as const;
    const onFirstGesture = () => {
      // 한 화면 이상 직접 내려본 뒤에만 - 첫 터치 직후 뜨면 "진입 직후"로 보인다.
      if (window.scrollY < window.innerHeight) return;
      gestures.forEach((g) => window.removeEventListener(g, onFirstGesture));
      timer = setTimeout(() => setOpen(true), OPEN_DELAY_MS);
    };
    gestures.forEach((g) => window.addEventListener(g, onFirstGesture, { passive: true }));
    return () => {
      gestures.forEach((g) => window.removeEventListener(g, onFirstGesture));
      if (timer) clearTimeout(timer);
    };
  }, []);

  useLockBodyScroll(open);

  if (!open) return null;

  const close = () => {
    markAsked();
    setOpen(false);
  };

  const handleAgree = () => {
    Analytics.click({ log_name: 'push_opt_in_prompt_click' });
    Notification.requestAgreement({
      options: { templateCode: TEMPLATE_CODE },
      onEvent: ({ type }) => {
        Analytics.click({ log_name: 'push_opt_in_result', result: type });
        if (type === 'newAgreement') grantPushReward();
        close();
      },
      onError: close,
    });
  };

  return (
    <div className="push-opt-in-backdrop">
      <div className="push-opt-in-dialog">
        <span className="push-opt-in-dialog__emoji tf">🔔</span>
        <span className="push-opt-in-dialog__title">특가 알림 받으시겠습니까?</span>
        <span className="push-opt-in-dialog__subtitle">매일 저녁 7시, 반값 이상 특가를 가장 먼저 알려드려요</span>
        <div className="push-opt-in-dialog__actions">
          <button type="button" className="push-opt-in-dialog__decline" onClick={close}>
            다음에요
          </button>
          <button type="button" className="push-opt-in-dialog__accept" onClick={handleAgree}>
            받을게요
          </button>
        </div>
      </div>
    </div>
  );
}
