import { Device } from '@apps-in-toss/web-framework';
import { ChevronRight } from './components/icons';
import type { Product } from './types';

export function Hero({ product }: { product: Product }) {
  const handleOpen = () => {
    Device.openURL(product.shareLink);
  };

  return (
    <button type="button" className="hero" onClick={handleOpen}>
      <img src={product.imageUrl} alt="" className="hero__image" />
      <div className="hero__overlay">
        <span className="hero__badge">오늘 최고 할인 {product.discountRate}%</span>
        <div className="hero__name">{product.name}</div>
        <div className="hero__footer">
          <span className="hero__price">{product.price.toLocaleString()}원</span>
          <span className="hero__cta">
            보러가기
            <ChevronRight size={16} />
          </span>
        </div>
      </div>
    </button>
  );
}
