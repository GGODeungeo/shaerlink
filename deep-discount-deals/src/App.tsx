import { useEffect, useState } from 'react';
import { ProductCard } from './ProductCard';
import { TopDealsCarousel } from './TopDealsCarousel';
import { Search } from './components/icons';
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

type SortKey = 'recommend' | 'discount' | 'price';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'recommend', label: '추천순' },
  { key: 'discount', label: '할인율순' },
  { key: 'price', label: '낮은 가격순' },
];

function sortProducts(products: Product[], sort: SortKey) {
  return [...products].sort((a, b) => {
    if (sort === 'discount') return b.discountRate - a.discountRate;
    if (sort === 'price') return a.price - b.price;
    return b.reviewCount - a.reviewCount;
  });
}

function App() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>('recommend');
  const [search, setSearch] = useState('');

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
          <div className="search-bar">
            <Search size={18} />
            <input
              type="text"
              className="search-bar__input"
              placeholder="상품명으로 검색"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
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
          const isSearching = search.trim().length > 0;
          const filteredProducts = isSearching
            ? state.products.filter((p) => p.name.toLowerCase().includes(search.trim().toLowerCase()))
            : state.products;

          if (filteredProducts.length === 0) {
            return (
              <p className="state-message">
                {isSearching ? '검색 결과가 없어요.' : '지금은 조건에 맞는 상품이 없어요.'}
              </p>
            );
          }

          const sortRow = (
            <div className="sort-row">
              <div className="sort-bar__group" role="group" aria-label="정렬">
                {SORT_OPTIONS.map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    className={
                      sort === option.key ? 'sort-bar__item sort-bar__item--active' : 'sort-bar__item'
                    }
                    onClick={() => setSort(option.key)}
                  >
                    <span className="sort-bar__item-label">{option.label}</span>
                  </button>
                ))}
              </div>
            </div>
          );

          if (isSearching) {
            return (
              <>
                {sortRow}
                <div className="product-grid">
                  {sortProducts(filteredProducts, sort).map((product) => (
                    <ProductCard key={product.shareLink} product={product} />
                  ))}
                </div>
              </>
            );
          }

          const groups = groupByCategory(filteredProducts);
          const activeLabel = selectedCategory ?? groups[0]?.label;
          const activeGroup = groups.find((g) => g.label === activeLabel);
          return (
            <>
              <TopDealsCarousel products={state.products} />

              <nav className="category-tabs" aria-label="카테고리">
                {groups.map((group) => (
                  <button
                    key={group.label}
                    type="button"
                    className={
                      group.label === activeLabel
                        ? 'category-tabs__item category-tabs__item--active'
                        : 'category-tabs__item'
                    }
                    onClick={() => setSelectedCategory(group.label)}
                  >
                    {group.label}
                  </button>
                ))}
              </nav>

              {sortRow}

              <div className="product-grid">
                {sortProducts(activeGroup?.products ?? [], sort).map((product) => (
                  <ProductCard key={product.shareLink} product={product} />
                ))}
              </div>
            </>
          );
        })()}

        <p className="disclosure">
          이 앱은 토스쇼핑 파트너스 활동의 일환으로, 상품 구매 시 일정액의 수수료를 제공받습니다.
        </p>
      </div>
    </div>
  );
}

export default App;
