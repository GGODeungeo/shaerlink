import { Device } from '@apps-in-toss/web-framework';
import type { Product } from './types';

export function ProductCard({ product }: { product: Product }) {
  const handleOpen = () => {
    Device.openURL(product.shareLink);
  };

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
      <div className="product-card__name">{product.name}</div>
    </button>
  );
}
