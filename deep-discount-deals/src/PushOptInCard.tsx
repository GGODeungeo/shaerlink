import { useState } from 'react';
import { Analytics, Notification } from '@apps-in-toss/web-framework';
import { ChevronRight } from './components/icons';
import { getAnonKey } from './trackedLink';

const TEMPLATE_CODE = 'hidden-deals-DAILY_DEAL_PUSH';
const STORAGE_KEY = 'hidden-deals:push-agreement-status';
const PUSH_REWARD_URL = 'https://shaerlink.vercel.app/api/push-reward';

type Status = 'asked' | null;

function readStatus(): Status {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'asked' ? 'asked' : null;
  } catch {
    return null;
  }
}

function writeStatus() {
  try {
    localStorage.setItem(STORAGE_KEY, 'asked');
  } catch {
    // 저장 공간이 없거나 접근이 막힌 환경 - 이번 세션에는 다시 물어봐도 무해함
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

export function PushOptInCard() {
  const [status, setStatus] = useState<Status>(readStatus);

  if (status === 'asked') return null;
  if (!Notification.requestAgreement.isSupported()) return null;

  const handleClick = () => {
    Analytics.click({ log_name: 'push_opt_in_card_click' });
    Notification.requestAgreement({
      options: { templateCode: TEMPLATE_CODE },
      onEvent: ({ type }) => {
        Analytics.click({ log_name: 'push_opt_in_result', result: type });
        if (type === 'newAgreement') grantPushReward();
        writeStatus();
        setStatus('asked');
      },
      onError: () => {
        // 사용자가 동의 화면 자체를 닫았거나 일시적 오류 - 다음에 다시 물어봄
      },
    });
  };

  return (
    <button type="button" className="push-opt-in-card" onClick={handleClick}>
      <span className="push-opt-in-card__emoji tf">🔔</span>
      <span className="push-opt-in-card__text">
        <span className="push-opt-in-card__title">특가 알림 받기</span>
        <span className="push-opt-in-card__subtitle">매일 저녁 7시, 반값 이상 특가를 가장 먼저 알려드려요</span>
      </span>
      <span className="push-opt-in-card__chevron">
        <ChevronRight size={18} />
      </span>
    </button>
  );
}
