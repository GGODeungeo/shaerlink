import { useEffect, useState } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import type { Product } from './types';

const TRENDING_KEYWORDS_URL = 'https://shaerlink.vercel.app/api/trending-keywords';

type TrendingItem = {
  keyword: string;
  searchChangePercent: number;
  product: Product;
};

/** "요즘 많이 찾는 상품" - 토스 검색 급상승 키워드 중 우리 카탈로그와 매칭된
 * 것만 가로 칩으로 보여준다. 매칭이 하나도 없으면(흔함 - 트렌드 키워드
 * 대부분은 우리가 안 파는 상품명) 섹션 자체를 숨긴다. */
export function TrendingKeywords({ onSelect }: { onSelect: (product: Product) => void }) {
  const [items, setItems] = useState<TrendingItem[]>([]);

  useEffect(() => {
    fetch(TRENDING_KEYWORDS_URL)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: TrendingItem[]) => setItems(data))
      .catch(() => setItems([]));
  }, []);

  if (items.length === 0) return null;

  return (
    <div className="category-shelf">
      <div className="category-shelf__header">
        <span className="category-shelf__title">
          <span className="tf">🔥</span> 요즘 많이 찾는 상품
        </span>
      </div>
      <div className="trending-keywords__list">
        {items.map((item) => (
          <button
            key={item.keyword}
            type="button"
            className="trending-keywords__chip"
            onClick={() => {
              Analytics.click({ log_name: 'trending_keyword_click', keyword: item.keyword });
              onSelect(item.product);
            }}
          >
            {item.keyword}
            <span className="trending-keywords__chip-percent">▲{Math.round(item.searchChangePercent)}%</span>
          </button>
        ))}
      </div>
    </div>
  );
}
