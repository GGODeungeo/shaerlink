import { dedupeByImage } from './dedupeByImage';
import { pickReason } from './pickReason';
import { reviewCountLabel } from './reviewCount';
import { savingsAmount } from './savings';
import type { Product } from './types';

const RANKING_SIZE = 30;

export function PopularRanking({
  products,
  onSelect,
}: {
  products: Product[];
  onSelect: (product: Product) => void;
}) {
  const ranked = dedupeByImage(
    [...products].sort((a, b) => b.reviewCount - a.reviewCount)
  ).slice(0, RANKING_SIZE);

  return (
    <div className="event-page">
      <h2 className="event-page__title">이런 이유로 골랐어요</h2>
      <p className="event-page__subtitle">가장 이득인 특가만 모았어요</p>

      {ranked.length === 0 ? (
        <p className="state-message">지금은 보여드릴 상품이 없어요.</p>
      ) : (
        <div className="reason-list">
          {ranked.map((product, i) => {
            const [title] = product.name.split(', ');
            const reviews = reviewCountLabel(product.reviewCount);
            return (
              <button
                key={product.shareLink}
                type="button"
                className="reason-card"
                onClick={() => onSelect(product)}
              >
                <div className="reason-card__rank">오늘의 추천 · {String(i + 1).padStart(2, '0')}</div>
                <div className="reason-card__reason">✅ {pickReason(product)}</div>
                <div className="reason-card__body">
                  <img src={product.imageUrl} alt={title} className="reason-card__image" loading="lazy" />
                  <div className="reason-card__info">
                    <span className="reason-card__title">{title}</span>
                    <span className="reason-card__discount">{product.discountRate}% 할인</span>
                    <span className="reason-card__price">{product.price.toLocaleString()}원</span>
                    <span className="reason-card__savings">▼ {savingsAmount(product).toLocaleString()}원 절약</span>
                    {reviews && <span className="reason-card__reviews">{reviews}</span>}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
