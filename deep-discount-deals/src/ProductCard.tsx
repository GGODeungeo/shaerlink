import { Device } from '@apps-in-toss/web-framework';
import type { Product } from './types';

function dealCountdownLabel(dealEndsAt: string | undefined): string | null {
  if (!dealEndsAt) return null;
  const msLeft = new Date(dealEndsAt).getTime() - Date.now();
  if (msLeft <= 0) return null;
  const hoursLeft = Math.ceil(msLeft / (60 * 60 * 1000));
  if (hoursLeft >= 1) return `${hoursLeft}시간 후 종료`;
  const minutesLeft = Math.max(1, Math.ceil(msLeft / (60 * 1000)));
  return `${minutesLeft}분 후 종료`;
}

export function ProductCard({ product }: { product: Product }) {
  const handleOpen = () => {
    Device.openURL(product.shareLink);
  };

  const [title, ...specs] = product.name.split(', ');
  const countdown = dealCountdownLabel(product.dealEndsAt);

  return (
    <button type="button" className="product-card" onClick={handleOpen}>
      <div className="product-card__image-wrap">
        <img src={product.imageUrl} alt="" className="product-card__image" />
      </div>
      <div className="product-card__badges">
        <span className="product-card__badge">{product.discountRate}% 특가</span>
        {countdown && <span className="product-card__badge product-card__badge--deal">{countdown}</span>}
      </div>
      <div className="product-card__price">{product.price.toLocaleString()}원</div>
      <div className="product-card__title">{title}</div>
      {specs.length > 0 && <div className="product-card__specs">{specs.join(' · ')}</div>}
    </button>
  );
}
