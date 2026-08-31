import { Device } from '@apps-in-toss/web-framework';
import type { Product } from './types';

export function ProductCard({ product }: { product: Product }) {
  const handleOpen = () => {
    Device.openURL(product.shareLink);
  };

  const [title, ...specs] = product.name.split(', ');

  return (
    <button type="button" className="product-card" onClick={handleOpen}>
      <div className="product-card__image-wrap">
        <img src={product.imageUrl} alt="" className="product-card__image" />
        <span className="product-card__badge">{product.discountRate}% 특가</span>
      </div>
      <div className="product-card__price-row">
        <span className="product-card__discount">{product.discountRate}%</span>
        <span className="product-card__price">{product.price.toLocaleString()}원</span>
      </div>
      <div className="product-card__title">{title}</div>
      {specs.length > 0 && <div className="product-card__specs">{specs.join(' · ')}</div>}
    </button>
  );
}
