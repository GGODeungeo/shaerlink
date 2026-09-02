import { useEffect, useMemo, useState } from 'react';
import { Device } from '@apps-in-toss/web-framework';
import type { Product } from './types';

const ROTATE_MS = 3500;
const TOP_N = 5;

export function TopDealsCarousel({ products }: { products: Product[] }) {
  const topDeals = useMemo(
    () => [...products].sort((a, b) => b.discountRate - a.discountRate).slice(0, TOP_N),
    [products]
  );
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (topDeals.length <= 1) return;
    const timer = setInterval(() => {
      setIndex((current) => (current + 1) % topDeals.length);
    }, ROTATE_MS);
    return () => clearInterval(timer);
  }, [topDeals.length]);

  const product = topDeals[index];
  if (!product) return null;

  const [title] = product.name.split(', ');

  return (
    <div className="carousel">
      <div className="carousel__label">오늘의 초특가</div>
      <button
        type="button"
        className="carousel__card"
        onClick={() => Device.openURL(product.shareLink)}
      >
        <div className="carousel__image-wrap">
          <img src={product.imageUrl} alt="" className="carousel__image" />
        </div>
        <div className="carousel__info">
          <span className="carousel__discount">{product.discountRate}% 특가</span>
          <span className="carousel__price">{product.price.toLocaleString()}원</span>
          <span className="carousel__name">{title}</span>
        </div>
      </button>
      <div className="carousel__dots">
        {topDeals.map((item, i) => (
          <span
            key={item.shareLink}
            className={i === index ? 'carousel__dot carousel__dot--active' : 'carousel__dot'}
          />
        ))}
      </div>
    </div>
  );
}
