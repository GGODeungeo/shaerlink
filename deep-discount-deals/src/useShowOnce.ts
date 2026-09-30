import { useEffect, useState } from 'react';

/** Whether a one-time UI element (banner, notice) should still show. True
 * until the first time it's rendered, then persisted as seen in
 * localStorage under `key` so it never comes back on a later app open -
 * this render still shows it once, uninterrupted. */
export function useShowOnce(key: string): boolean {
  const [alreadySeen] = useState(() => {
    try {
      return localStorage.getItem(key) === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    if (alreadySeen) return;
    try {
      localStorage.setItem(key, '1');
    } catch {
      // 저장 공간이 없거나 접근이 막힌 환경 - 다음에 다시 보여도 무해함
    }
  }, [alreadySeen, key]);

  return !alreadySeen;
}
