import { useEffect, useMemo, useRef, useState } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import { dedupeByImage } from './dedupeByImage';
import { savingsAmount } from './savings';
import type { Product } from './types';

const ROTATE_MS = 3500;
const POOL_MIN_DISCOUNT = 80;
const POOL_SIZE = 20;
const GROUP_SIZE = 5;

export function TopDealsCarousel({
  products,
  onSelect,
}: {
  products: Product[];
  onSelect: (product: Product) => void;
}) {
  const [brokenImages, setBrokenImages] = useState<Set<string>>(new Set());

  const pool = useMemo(
    () =>
      dedupeByImage(
        [...products]
          .filter((p) => p.discountRate >= POOL_MIN_DISCOUNT)
          .sort((a, b) => b.reviewCount - a.reviewCount)
      ).slice(0, POOL_SIZE),
    [products]
  );

  const chunks = useMemo(() => {
    const result: Product[][] = [];
    for (let i = 0; i < pool.length; i += GROUP_SIZE) {
      result.push(pool.slice(i, i + GROUP_SIZE));
    }
    return result;
  }, [pool]);

  const [chunkIndex] = useState(() => Math.floor(Math.random() * Math.max(chunks.length, 1)));

  const topDeals = useMemo(
    () => (chunks[chunkIndex] ?? []).filter((p) => !brokenImages.has(p.shareLink)),
    [chunks, chunkIndex, brokenImages]
  );

  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (topDeals.length <= 1) return;
    const timer = setInterval(() => {
      setIndex((current) => (current + 1) % topDeals.length);
    }, ROTATE_MS);
    return () => clearInterval(timer);
  }, [topDeals.length]);

  const touchStartX = useRef<number | null>(null);
  const didSwipe = useRef(false);
  const SWIPE_THRESHOLD = 40;

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX.current === null || topDeals.length <= 1) return;
    const deltaX = e.changedTouches[0].clientX - touchStartX.current;
    touchStartX.current = null;
    if (deltaX > SWIPE_THRESHOLD) {
      didSwipe.current = true;
      setIndex((current) => (current - 1 + topDeals.length) % topDeals.length);
    } else if (deltaX < -SWIPE_THRESHOLD) {
      didSwipe.current = true;
      setIndex((current) => (current + 1) % topDeals.length);
    }
  };

  const product = topDeals[index];
  if (!product) return null;

  const [title] = product.name.split(', ');

  const handleClick = () => {
    if (didSwipe.current) {
      didSwipe.current = false;
      return;
    }
    Analytics.click({
      log_name: 'top_deal_card_click',
      product_name: product.name,
      product_category: product.category,
      discount_rate: product.discountRate,
      price: product.price,
    });
    onSelect(product);
  };

  return (
    <div className="carousel">
      <button
        type="button"
        className="carousel__card"
        onClick={handleClick}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <div className="carousel__image-wrap">
          <img src={product.imageUrl} alt="" className="carousel__image-backdrop" aria-hidden="true" />
          <img
            src={product.imageUrl}
            alt={title}
            className="carousel__image"
            decoding="async"
            onError={() =>
              setBrokenImages((prev) => new Set(prev).add(product.shareLink))
            }
          />
          <div className="carousel__scrim" />
          <div className="carousel__overlay">
            <span className="carousel__discount">{product.discountRate}% 특가</span>
            <span className="carousel__name">{title}</span>
            <span className="carousel__price">
              {product.price.toLocaleString()}원
              <span className="carousel__savings"> · {savingsAmount(product).toLocaleString()}원 아껴요</span>
            </span>
          </div>
          {topDeals.length > 1 && (
            <span className="carousel__counter">{index + 1} | {topDeals.length}</span>
          )}
        </div>
      </button>
    </div>
  );
}
