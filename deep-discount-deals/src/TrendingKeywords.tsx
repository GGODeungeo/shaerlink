import { useEffect, useState } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import type { Product } from './types';

const TRENDING_KEYWORDS_URL = 'https://shaerlink.vercel.app/api/trending-keywords';
const ROTATE_INTERVAL_MS = 2500;

type TrendingItem = {
  keyword: string;
  searchChangePercent: number;
  product: Product;
};

/** "요즘 많이 찾는 상품" - 토스 검색 급상승 키워드 중 우리 카탈로그와 매칭된
 * 것만 실시간 검색어 순위처럼 한 줄씩 자동으로 넘어가며 보여준다. 매칭이
 * 하나도 없으면(흔함 - 트렌드 키워드 대부분은 우리가 안 파는 상품명) 섹션
 * 자체를 숨긴다. */
export function TrendingKeywords({ onSelect }: { onSelect: (product: Product) => void }) {
  const [items, setItems] = useState<TrendingItem[]>([]);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    fetch(TRENDING_KEYWORDS_URL)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: TrendingItem[]) => setItems(data))
      .catch(() => setItems([]));
  }, []);

  useEffect(() => {
    if (items.length <= 1) return;
    const timer = setInterval(() => setIndex((i) => (i + 1) % items.length), ROTATE_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [items.length]);

  if (items.length === 0) return null;

  const current = items[index];

  return (
    <div className="category-shelf">
      <div className="category-shelf__header">
        <span className="category-shelf__title">
          <span className="tf">🔥</span> 요즘 많이 찾는 상품
        </span>
      </div>
      <button
        type="button"
        className="trending-ticker"
        onClick={() => {
          Analytics.click({ log_name: 'trending_keyword_click', keyword: current.keyword });
          onSelect(current.product);
        }}
      >
        <span className="trending-ticker__rank">{String(index + 1).padStart(2, '0')}</span>
        <span key={current.keyword} className="trending-ticker__row">
          <span className="trending-ticker__keyword">{current.keyword}</span>
          <span className="trending-ticker__percent">▲{Math.round(current.searchChangePercent)}%</span>
        </span>
      </button>
    </div>
  );
}
