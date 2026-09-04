import { useEffect, useState } from 'react';
import { ChevronLeft } from './components/icons';
import { ProductCard } from './ProductCard';
import { dedupeByImage } from './dedupeByImage';
import type { Product } from './types';

const EVENT_HOUR = 9;
const EVENT_SIZE = 10;

function todayAt(hour: number): number {
  const d = new Date();
  d.setHours(hour, 0, 0, 0);
  return d.getTime();
}

function countdownLabel(msLeft: number): string {
  const totalMinutes = Math.max(1, Math.ceil(msLeft / (60 * 1000)));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `${hours}시간 ${minutes}분 후 공개` : `${minutes}분 후 공개`;
}

export function TodaysPickEvent({
  products,
  onSelect,
  onBack,
  favorites,
  onToggleFavorite,
}: {
  products: Product[];
  onSelect: (product: Product) => void;
  onBack: () => void;
  favorites: Set<string>;
  onToggleFavorite: (shareLink: string) => void;
}) {
  const [now, setNow] = useState(() => Date.now());
  const eventStart = todayAt(EVENT_HOUR);
  const unlocked = now >= eventStart;

  useEffect(() => {
    if (unlocked) return;
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, [unlocked]);

  const eventProducts = dedupeByImage(
    [...products].sort((a, b) => b.reviewCount - a.reviewCount)
  ).slice(0, EVENT_SIZE);

  return (
    <>
      <button type="button" className="back-to-home" onClick={onBack}>
        <ChevronLeft size={16} /> 홈
      </button>

      <div className="event-page">
        <h2 className="event-page__title">오늘의 특가 오픈 이벤트</h2>
        <p className="event-page__subtitle">구매평 많고 반응 좋은 상품만 모았어요</p>

        {!unlocked ? (
          <div className="event-page__locked">
            <p className="event-page__countdown">{countdownLabel(eventStart - now)}</p>
            <p className="event-page__locked-hint">매일 오전 9시에 공개돼요</p>
          </div>
        ) : eventProducts.length === 0 ? (
          <p className="state-message">지금은 보여드릴 상품이 없어요.</p>
        ) : (
          <div className="product-grid">
            {eventProducts.map((product) => (
              <ProductCard
                key={product.shareLink}
                product={product}
                onSelect={onSelect}
                isFavorite={favorites.has(product.shareLink)}
                onToggleFavorite={onToggleFavorite}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
