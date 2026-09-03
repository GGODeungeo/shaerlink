import { useCallback, useState } from 'react';

const STORAGE_KEY = 'hidden-deals:recently-viewed';
const MAX_ITEMS = 20;

function readStored(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function writeStored(ids: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // 저장 공간이 없거나 접근이 막힌 환경 - 이번 세션 동안만 메모리로 유지
  }
}

export function useRecentlyViewed() {
  const [recentIds, setRecentIds] = useState<string[]>(readStored);

  const recordView = useCallback((shareLink: string) => {
    setRecentIds((current) => {
      const next = [shareLink, ...current.filter((id) => id !== shareLink)].slice(0, MAX_ITEMS);
      writeStored(next);
      return next;
    });
  }, []);

  return { recentIds, recordView };
}
