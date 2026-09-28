import { useState } from 'react';

const STORAGE_KEY = 'hidden-deals:review-submitted';

function readSubmitted(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

function writeSubmitted() {
  try {
    localStorage.setItem(STORAGE_KEY, 'true');
  } catch {
    // 저장 공간이 없거나 접근이 막힌 환경 - 이번 세션엔 카드가 다시 떠도 무해함
  }
}

export function useReviewPrompt() {
  const [submitted, setSubmitted] = useState<boolean>(readSubmitted);

  const markSubmitted = () => {
    writeSubmitted();
    setSubmitted(true);
  };

  return { submitted, markSubmitted };
}
