import { Analytics, Device, Share } from '@apps-in-toss/web-framework';
import { Close } from './components/icons';
import { savingsAmount } from './savings';
import { useLockBodyScroll } from './useLockBodyScroll';
import type { Product } from './types';

export function PurchaseSheet({
  product,
  onClose,
}: {
  product: Product;
  onClose: () => void;
}) {
  useLockBodyScroll();

  const [title] = product.name.split(', ');

  const handleConfirm = () => {
    Analytics.click({
      log_name: 'purchase_cta_click',
      product_name: product.name,
      product_category: product.category,
      discount_rate: product.discountRate,
      price: product.price,
    });
    onClose();
    Device.openURL(product.shareLink);
  };

  const handleShare = async () => {
    Analytics.click({
      log_name: 'share_button_click',
      product_name: product.name,
      product_category: product.category,
      discount_rate: product.discountRate,
    });
    try {
      const link = await Share.createLink({ path: 'intoss://hidden-deals' });
      await Share.sendMessage({
        message: `${title} ${product.discountRate}% 특가!\n반값 이상 특가를 숨은특가에서 확인해보세요.\n${link}`,
      });
    } catch {
      // 사용자가 공유 시트를 취소했거나 네트워크 오류 - 조용히 무시
    }
  };

  return (
    <div className="purchase-sheet-backdrop" onClick={onClose}>
      <div className="purchase-sheet" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="purchase-sheet__close" onClick={onClose} aria-label="닫기">
          <Close size={18} />
        </button>

        <div className="purchase-sheet__product">
          <img src={product.imageUrl} alt={title} className="purchase-sheet__image" />
          <div className="purchase-sheet__info">
            <span className="purchase-sheet__discount">{product.discountRate}% 특가</span>
            <span className="purchase-sheet__price">{product.price.toLocaleString()}원</span>
            <span className="purchase-sheet__savings">▼ {savingsAmount(product).toLocaleString()}원 아껴요</span>
            <span className="purchase-sheet__name">{title}</span>
          </div>
        </div>

        <button type="button" className="purchase-sheet__cta" onClick={handleConfirm}>
          토스쇼핑에서 구매하기
        </button>

        <button type="button" className="purchase-sheet__share" onClick={handleShare}>
          친구에게 공유하기
        </button>

        <p className="purchase-sheet__hint">
          구매하고 나면, 새로 올라온 반값 특가들 보러 또 놀러오세요!
        </p>
      </div>
    </div>
  );
}
