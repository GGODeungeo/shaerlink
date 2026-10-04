import { useEffect, useState } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import { ChevronDown, ChevronUp } from './components/icons';
import type { Product } from './types';

const TRENDING_KEYWORDS_URL = 'https://shaerlink.vercel.app/api/trending-keywords';
const SWEEP_INTERVAL_MS = 1200;
const COLLAPSED_COUNT = 5;

type TrendingItem = {
  keyword: string;
  searchChangePercent: number;
  product: Product;
};

function TrendingRow({
  item,
  rank,
  active,
  onSelect,
}: {
  item: TrendingItem;
  rank: number;
  active: boolean;
  onSelect: (product: Product) => void;
}) {
  return (
    <button
      type="button"
      className={active ? 'trending-list__row trending-list__row--active' : 'trending-list__row'}
      onClick={() => {
        Analytics.click({ log_name: 'trending_keyword_click', keyword: item.keyword });
        onSelect(item.product);
      }}
    >
      <span className="trending-list__rank">{String(rank).padStart(2, '0')}</span>
      <span className="trending-list__keyword">{item.keyword}</span>
      <span className="trending-list__percent">▲{Math.round(item.searchChangePercent)}%</span>
    </button>
  );
}

/** "요즘 많이 찾는 상품" - 토스 검색 급상승 키워드 중 우리 카탈로그와 매칭된
 * 것만 순위 리스트로 보여준다. 실제 데이터는 하루 한 번(크론) 갱신되지만,
 * 한 줄씩 훑는 하이라이트 애니메이션으로 "계속 갱신되고 있다"는 느낌을 준다
 * - 순위 자체를 뒤섞거나 가짜 숫자를 보여주진 않는다. 기본 5개만 보이고,
 * "더보기"를 누르면 나머지가 펼쳐진다(다시 누르면 접힘). 매칭이 하나도
 * 없으면(흔함 - 트렌드 키워드 대부분은 우리가 안 파는 상품명) 섹션 자체를
 * 숨긴다. */
export function TrendingKeywords({ onSelect }: { onSelect: (product: Product) => void }) {
  const [items, setItems] = useState<TrendingItem[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    fetch(TRENDING_KEYWORDS_URL)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: TrendingItem[]) => setItems(data))
      .catch(() => setItems([]));
  }, []);

  useEffect(() => {
    if (items.length <= 1) return;
    const timer = setInterval(() => setActiveIndex((i) => (i + 1) % items.length), SWEEP_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [items.length]);

  if (items.length === 0) return null;

  const visible = items.slice(0, COLLAPSED_COUNT);
  const rest = items.slice(COLLAPSED_COUNT);

  return (
    <div className="category-shelf">
      <div className="category-shelf__header">
        <span className="category-shelf__title">
          <span className="tf">🔥</span> 요즘 많이 찾는 상품
          <span className="trending-live-dot" aria-hidden="true" />
        </span>
      </div>
      <div className="trending-list">
        {visible.map((item, i) => (
          <TrendingRow key={item.keyword} item={item} rank={i + 1} active={i === activeIndex} onSelect={onSelect} />
        ))}
        {rest.length > 0 && (
          <div className={expanded ? 'trending-list__more trending-list__more--open' : 'trending-list__more'}>
            <div className="trending-list__more-inner">
              {rest.map((item, i) => (
                <TrendingRow
                  key={item.keyword}
                  item={item}
                  rank={i + COLLAPSED_COUNT + 1}
                  active={i + COLLAPSED_COUNT === activeIndex}
                  onSelect={onSelect}
                />
              ))}
            </div>
          </div>
        )}
      </div>
      {rest.length > 0 && (
        <button type="button" className="trending-list__toggle" onClick={() => setExpanded((e) => !e)}>
          {expanded ? '접기' : '더보기'}
          {expanded ? <ChevronUp /> : <ChevronDown />}
        </button>
      )}
    </div>
  );
}
