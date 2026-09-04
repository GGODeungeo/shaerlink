import { useCallback, useState } from 'react';

const STORAGE_KEY = 'hidden-deals:recently-viewed';
const MAX_ITEMS = 20;
const EXPIRY_MS = 3 * 24 * 60 * 60 * 1000; // 3일 지난 기록은 굳이 안 보여준다 - 계속 쌓이기만 하면 오히려 안 쓰는 기능처럼 보인다

type Entry = { shareLink: string; viewedAt: number };

function pruneExpired(entries: Entry[]): Entry[] {
  const cutoff = Date.now() - EXPIRY_MS;
  return entries.filter((e) => e.viewedAt >= cutoff);
}

function readStored(): Entry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    // 예전 포맷(string[])으로 저장된 기록 - viewedAt이 없으니 지금 시각으로 채워 한 번은 그대로 살려준다
    if (Array.isArray(parsed) && typeof parsed[0] === 'string') {
      return parsed.map((shareLink: string) => ({ shareLink, viewedAt: Date.now() }));
    }
    return pruneExpired(parsed);
  } catch {
    return [];
  }
}

function writeStored(entries: Entry[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // 저장 공간이 없거나 접근이 막힌 환경 - 이번 세션 동안만 메모리로 유지
  }
}

export function useRecentlyViewed() {
  const [entries, setEntries] = useState<Entry[]>(readStored);

  const recordView = useCallback((shareLink: string) => {
    setEntries((current) => {
      const next = pruneExpired([
        { shareLink, viewedAt: Date.now() },
        ...current.filter((e) => e.shareLink !== shareLink),
      ]).slice(0, MAX_ITEMS);
      writeStored(next);
      return next;
    });
  }, []);

  const removeView = useCallback((shareLink: string) => {
    setEntries((current) => {
      const next = current.filter((e) => e.shareLink !== shareLink);
      writeStored(next);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    setEntries([]);
    writeStored([]);
  }, []);

  return {
    recentIds: entries.map((e) => e.shareLink),
    recordView,
    removeView,
    clearAll,
  };
}
