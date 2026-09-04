import { useState } from 'react';
import { Analytics, Notification } from '@apps-in-toss/web-framework';

const TEMPLATE_CODE = 'hidden-deals-DAILY_DEAL_PUSH';
const STORAGE_KEY = 'hidden-deals:push-agreement-status';

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
        <span className="push-opt-in-card__subtitle">매일 저녁 7시, 반값 특가를 알려드려요</span>
      </span>
    </button>
  );
}
