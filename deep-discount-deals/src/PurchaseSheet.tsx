import { useState } from 'react';
import { Analytics, Device, Share } from '@apps-in-toss/web-framework';
import { Close } from './components/icons';
import { savingsAmount } from './savings';
import { reviewCountLabel } from './reviewCount';
import { useLockBodyScroll } from './useLockBodyScroll';
import { getTrackedPurchaseUrl } from './trackedLink';
import { requestReviewOnce } from './reviewPrompt';
import type { Product } from './types';

export function PurchaseSheet({
  product,
  onClose,
}: {
  product: Product;
  onClose: () => void;
}) {
  useLockBodyScroll();

  const [active, setActive] = useState(product);
  const options = product.variants ?? [];

  const [title] = active.name.split(', ');
  const reviews = reviewCountLabel(active.reviewCount);

  const handleConfirm = async () => {
    Analytics.click({
      log_name: 'purchase_cta_click',
      product_name: active.name,
      product_category: active.category,
      discount_rate: active.discountRate,
      price: active.price,
    });
    onClose();
    await requestReviewOnce();
    Device.openURL(await getTrackedPurchaseUrl(active));
  };

  const handleShare = async () => {
    Analytics.click({
      log_name: 'share_button_click',
      product_name: active.name,
      product_category: active.category,
      discount_rate: active.discountRate,
    });
    try {
      const link = await Share.createLink({
        path: 'intoss://hidden-deals',
        ogImageUrl: 'https://static.toss.im/appsintoss/61293/06a91316-51e4-4209-892a-28b136d4436a.png',
      });
      await Share.sendMessage({
        message: `${title} ${active.discountRate}% 특가!\n반값 이상 특가를 숨은특가에서 확인해보세요.\n${link}`,
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
          <img src={active.imageUrl} alt={title} className="purchase-sheet__image" />
          <div className="purchase-sheet__info">
            <span className="purchase-sheet__discount">{active.discountRate}% 특가</span>
            <span className="purchase-sheet__price">{active.price.toLocaleString()}원</span>
            <span className="purchase-sheet__savings">▼ {savingsAmount(active).toLocaleString()}원 아껴요</span>
            <span className="purchase-sheet__name">{title}</span>
            {reviews && <span className="purchase-sheet__reviews">{reviews}</span>}
          </div>
        </div>

        {options.length > 1 && (
          <div className="purchase-sheet__variants">
            {options
              .slice()
              .sort((a, b) => a.price - b.price)
              .map((option) => (
                <button
                  key={option.shareLink}
                  type="button"
                  className="purchase-sheet__variant"
                  data-active={option.shareLink === active.shareLink}
                  onClick={() => setActive(option)}
                >
                  {option.name.split(', ').slice(1).join(', ')} · {option.price.toLocaleString()}원
                </button>
              ))}
          </div>
        )}

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
