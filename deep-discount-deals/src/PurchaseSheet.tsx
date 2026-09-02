import { Device } from '@apps-in-toss/web-framework';
import { Close } from './components/icons';
import type { Product } from './types';

export function PurchaseSheet({
  product,
  onClose,
}: {
  product: Product;
  onClose: () => void;
}) {
  const [title] = product.name.split(', ');

  const handleConfirm = () => {
    onClose();
    Device.openURL(product.shareLink);
  };

  return (
    <div className="purchase-sheet-backdrop" onClick={onClose}>
      <div className="purchase-sheet" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="purchase-sheet__close" onClick={onClose} aria-label="닫기">
          <Close size={18} />
        </button>

        <div className="purchase-sheet__product">
          <img src={product.imageUrl} alt="" className="purchase-sheet__image" />
          <div className="purchase-sheet__info">
            <span className="purchase-sheet__discount">{product.discountRate}% 특가</span>
            <span className="purchase-sheet__price">{product.price.toLocaleString()}원</span>
            <span className="purchase-sheet__name">{title}</span>
          </div>
        </div>

        <button type="button" className="purchase-sheet__cta" onClick={handleConfirm}>
          토스쇼핑에서 구매하기
        </button>

        <p className="purchase-sheet__hint">
          구매하고 나면, 새로 올라온 반값 특가들 보러 또 놀러오세요!
        </p>
      </div>
    </div>
  );
}
