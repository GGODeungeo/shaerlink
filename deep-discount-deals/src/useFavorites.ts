import { useCallback, useState } from 'react';

const STORAGE_KEY = 'hidden-deals:favorites';

function readStoredFavorites(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function writeStoredFavorites(favorites: Set<string>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...favorites]));
  } catch {
    // 저장 공간이 없거나 접근이 막힌 환경 - 이번 세션 동안만 메모리로 유지
  }
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<Set<string>>(readStoredFavorites);

  const toggleFavorite = useCallback((shareLink: string) => {
    setFavorites((current) => {
      const next = new Set(current);
      if (next.has(shareLink)) {
        next.delete(shareLink);
      } else {
        next.add(shareLink);
      }
      writeStoredFavorites(next);
      return next;
    });
  }, []);

  return { favorites, toggleFavorite };
}
