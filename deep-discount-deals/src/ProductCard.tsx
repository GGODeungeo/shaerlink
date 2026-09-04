import { useEffect, useState } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import { Heart } from './components/icons';
import type { Product } from './types';

function dealCountdownLabel(dealEndsAt: string | undefined, now: number): string | null {
  if (!dealEndsAt) return null;
  const msLeft = new Date(dealEndsAt).getTime() - now;
  if (msLeft <= 0) return null;
  const minutesLeft = Math.max(1, Math.ceil(msLeft / (60 * 1000)));
  if (minutesLeft >= 60) return `${Math.floor(minutesLeft / 60)}시간 후 종료`;
  return `${minutesLeft}분 후 종료`;
}

export function ProductCard({
  product,
  onSelect,
  isFavorite,
  onToggleFavorite,
}: {
  product: Product;
  onSelect: (product: Product) => void;
  isFavorite: boolean;
  onToggleFavorite: (shareLink: string) => void;
}) {
  const handleOpen = () => {
    Analytics.click({
      log_name: 'product_card_click',
      product_name: product.name,
      product_category: product.category,
      discount_rate: product.discountRate,
      price: product.price,
    });
    onSelect(product);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleOpen();
    }
  };

  const handleToggleFavorite = (e: React.MouseEvent) => {
    e.stopPropagation();
    Analytics.click({
      log_name: 'favorite_toggle_click',
      product_name: product.name,
      favorited: !isFavorite,
    });
    onToggleFavorite(product.shareLink);
  };

  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!product.dealEndsAt) return;
    const timer = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, [product.dealEndsAt]);

  const [title, ...specs] = product.name.split(', ');
  const countdown = dealCountdownLabel(product.dealEndsAt, now);

  return (
    <div
      className="product-card"
      role="button"
      tabIndex={0}
      onClick={handleOpen}
      onKeyDown={handleKeyDown}
    >
      <div className="product-card__image-wrap">
        <img
          src={product.imageUrl}
          alt={title}
          className="product-card__image"
          loading="lazy"
          decoding="async"
        />
        <button
          type="button"
          className="product-card__favorite"
          data-active={isFavorite}
          aria-label={isFavorite ? '찜 해제하기' : '찜하기'}
          onClick={handleToggleFavorite}
        >
          <Heart size={18} filled={isFavorite} />
        </button>
      </div>
      <div className="product-card__badges">
        {product.isAllTimeLow && (
          <span className="product-card__badge product-card__badge--lowest">
            <span className="tf">🔥</span> 역대 최저가
          </span>
        )}
        <span className="product-card__badge">{product.discountRate}% 특가</span>
        {countdown && <span className="product-card__badge product-card__badge--deal">{countdown}</span>}
      </div>
      <div className="product-card__price">{product.price.toLocaleString()}원</div>
      <div className="product-card__title">{title}</div>
      {specs.length > 0 && <div className="product-card__specs">{specs.join(' · ')}</div>}
    </div>
  );
}
