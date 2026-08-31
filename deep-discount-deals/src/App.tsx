import { useEffect, useState } from 'react';
import { CategoryNav } from './CategoryNav';
import { ProductCard } from './ProductCard';
import type { Product } from './types';
import './App.css';

const DATA_URL =
  'https://raw.githubusercontent.com/GGODeungeo/shaerlink/main/app-data/products.json';

function groupByCategory(products: Product[]) {
  const byCategory = new Map<string, Product[]>();
  for (const product of products) {
    const list = byCategory.get(product.category) ?? [];
    list.push(product);
    byCategory.set(product.category, list);
  }
  return [...byCategory.entries()]
    .map(([category, items]) => ({ label: category, products: items }))
    .sort((a, b) => b.products.length - a.products.length);
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'ready'; products: Product[] };

type SortKey = 'discount' | 'price';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'discount', label: '할인율순' },
  { key: 'price', label: '가격순' },
];

function sortProducts(products: Product[], sort: SortKey) {
  return [...products].sort((a, b) =>
    sort === 'discount' ? b.discountRate - a.discountRate : a.price - b.price
  );
}

function App() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>('discount');

  const fetchProducts = () => {
    fetch(DATA_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((products: Product[]) => setState({ status: 'ready', products }))
      .catch(() => setState({ status: 'error' }));
  };

  useEffect(fetchProducts, []);

  const retry = () => {
    setState({ status: 'loading' });
    fetchProducts();
  };

  return (
    <div className="canvas bg-canvas">
      <div className="page-container">
        <header className="page-header">
          <h1>반값 이상 특가</h1>
        </header>

        {state.status === 'loading' && <p className="state-message">불러오는 중...</p>}

        {state.status === 'error' && (
          <div className="state-message">
            <p>상품을 불러오지 못했어요.</p>
            <button type="button" className="retry-button" onClick={retry}>
              다시 시도
            </button>
          </div>
        )}

        {state.status === 'ready' && (() => {
          const groups = groupByCategory(state.products);
          const activeLabel = selectedCategory ?? groups[0]?.label;
          const activeGroup = groups.find((g) => g.label === activeLabel);
          return (
            <div className="shop">
              <CategoryNav
                categories={groups.map((g) => g.label)}
                selected={activeLabel}
                onSelect={setSelectedCategory}
              />
              <div className="shop-content">
                <div className="shop-content__header">
                  <h2 className="shop-content__title">{activeLabel}</h2>
                  <div className="sort-bar" role="group" aria-label="정렬">
                    {SORT_OPTIONS.map((option) => (
                      <button
                        key={option.key}
                        type="button"
                        className={
                          sort === option.key ? 'sort-bar__item sort-bar__item--active' : 'sort-bar__item'
                        }
                        onClick={() => setSort(option.key)}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="product-grid">
                  {sortProducts(activeGroup?.products ?? [], sort).map((product) => (
                    <ProductCard key={product.shareLink} product={product} />
                  ))}
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}

export default App;
