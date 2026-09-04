import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import { Bag, Close } from './components/icons';
import type { Product } from './types';

const AUTO_CLOSE_MS = 3000;
const EXIT_ANIMATION_MS = 300;

export type RecentlyViewedWidgetHandle = {
  open: () => void;
};

export const RecentlyViewedWidget = forwardRef<
  RecentlyViewedWidgetHandle,
  {
    products: Product[];
    onSelect: (product: Product) => void;
    onRemove: (shareLink: string) => void;
  }
>(function RecentlyViewedWidget({ products, onSelect, onRemove }, ref) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const autoCloseTimer = useRef<ReturnType<typeof setTimeout>>();
  const unmountTimer = useRef<ReturnType<typeof setTimeout>>();

  const clearTimers = () => {
    clearTimeout(autoCloseTimer.current);
    clearTimeout(unmountTimer.current);
  };

  useEffect(() => clearTimers, []);

  const openPanel = () => {
    clearTimers();
    setMounted(true);
    requestAnimationFrame(() => setOpen(true));
    autoCloseTimer.current = setTimeout(closePanel, AUTO_CLOSE_MS);
  };

  const closePanel = () => {
    clearTimeout(autoCloseTimer.current);
    setOpen(false);
    unmountTimer.current = setTimeout(() => setMounted(false), EXIT_ANIMATION_MS);
  };

  useImperativeHandle(ref, () => ({
    open: () => {
      Analytics.click({ log_name: 'recently_viewed_widget_open', item_count: products.length });
      openPanel();
    },
  }));

  if (products.length === 0) return null;

  const toggle = () => {
    if (mounted) {
      closePanel();
      return;
    }
    Analytics.click({ log_name: 'recently_viewed_widget_open', item_count: products.length });
    openPanel();
  };

  const total = products.reduce((sum, p) => sum + p.price, 0);

  return (
    <div className="recently-viewed-widget">
      {mounted && (
        <div className={open ? 'recently-viewed-panel recently-viewed-panel--visible' : 'recently-viewed-panel'}>
          <div className="recently-viewed-panel__header">
            <span>최근 본 상품 ({products.length})</span>
            <span className="recently-viewed-panel__total">합계 {total.toLocaleString()}원</span>
          </div>
          <div className="recently-viewed-panel__list">
            {products.map((product) => (
              <div key={product.shareLink} className="recently-viewed-panel__item">
                <button
                  type="button"
                  className="recently-viewed-panel__item-select"
                  onClick={() => {
                    closePanel();
                    onSelect(product);
                  }}
                >
                  <img
                    src={product.imageUrl}
                    alt={product.name.split(', ')[0]}
                    loading="lazy"
                    decoding="async"
                  />
                  <span className="recently-viewed-panel__price">{product.price.toLocaleString()}원</span>
                </button>
                <button
                  type="button"
                  className="recently-viewed-panel__item-remove"
                  aria-label="최근 본 목록에서 지우기"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove(product.shareLink);
                  }}
                >
                  <Close size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        type="button"
        className="recently-viewed-fab"
        aria-label={open ? '최근 본 상품 닫기' : '최근 본 상품 보기'}
        onClick={toggle}
      >
        {open ? <Close size={22} /> : <Bag size={22} />}
        {!open && <span className="recently-viewed-fab__badge">{products.length}</span>}
      </button>
    </div>
  );
});
