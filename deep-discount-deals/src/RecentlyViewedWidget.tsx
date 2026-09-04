import { useState } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import { Bag, Close } from './components/icons';
import type { Product } from './types';

export function RecentlyViewedWidget({
  products,
  onSelect,
}: {
  products: Product[];
  onSelect: (product: Product) => void;
}) {
  const [open, setOpen] = useState(false);

  if (products.length === 0) return null;

  const toggle = () => {
    if (!open) {
      Analytics.click({ log_name: 'recently_viewed_widget_open', item_count: products.length });
    }
    setOpen((current) => !current);
  };

  const total = products.reduce((sum, p) => sum + p.price, 0);

  return (
    <div className="recently-viewed-widget">
      {open && (
        <div className="recently-viewed-panel">
          <div className="recently-viewed-panel__header">
            <span>최근 본 상품 ({products.length})</span>
            <span className="recently-viewed-panel__total">합계 {total.toLocaleString()}원</span>
          </div>
          <div className="recently-viewed-panel__list">
            {products.map((product) => (
              <button
                key={product.shareLink}
                type="button"
                className="recently-viewed-panel__item"
                onClick={() => {
                  setOpen(false);
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
}
