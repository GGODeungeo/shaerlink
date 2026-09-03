import { useEffect, useState } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import { ProductCard } from './ProductCard';
import { TopDealsCarousel } from './TopDealsCarousel';
import { PurchaseSheet } from './PurchaseSheet';
import { ChevronLeft, Heart, Search } from './components/icons';
import { useFavorites } from './useFavorites';
import { useRecentlyViewed } from './useRecentlyViewed';
import type { Product } from './types';
import './App.css';

const DATA_URL =
  'https://raw.githubusercontent.com/GGODeungeo/shaerlink/main/app-data/products.json';

const CATEGORY_EMOJI: Record<string, string> = {
  '식품': '🍎',
  '가구/홈데코': '🛋️',
  '가전/디지털': '📱',
  '뷰티': '💄',
  '생활용품': '🧻',
  '스포츠/레져': '⚽',
  '자동차용품': '🚗',
  '주방용품': '🍳',
  '완구/취미': '🧸',
  '반려/애완용품': '🐾',
  '패션의류잡화': '👕',
  '문구/오피스': '📎',
  '음반/DVD': '💿',
  '출산/유아동': '🍼',
  '도서': '📚',
  '여행/취미': '✈️',
};
const DEFAULT_CATEGORY_EMOJI = '🏷️';
const SHELF_SIZE = 10;

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

const PAGE_SIZE = 20;

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
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [viewingFavorites, setViewingFavorites] = useState(false);
  const { favorites, toggleFavorite } = useFavorites();
  const { recentIds, recordView } = useRecentlyViewed();

  const handleSelectProduct = (product: Product) => {
    recordView(product.shareLink);
    setSelectedProduct(product);
  };

  const selectCategory = (label: string) => {
    setSelectedCategory(label);
    setViewingFavorites(false);
    setVisibleCount(PAGE_SIZE);
  };

  const openFavorites = () => {
    Analytics.click({ log_name: 'favorites_nav_click', favorite_count: favorites.size });
    setViewingFavorites(true);
    setVisibleCount(PAGE_SIZE);
  };

  const closeFavorites = () => {
    setViewingFavorites(false);
    setVisibleCount(PAGE_SIZE);
  };

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
          <div className="page-header__row">
            <h1>반값 이상 특가</h1>
            <button
              type="button"
              className="favorites-nav-button"
              data-active={favorites.size > 0}
              aria-label="찜한 상품"
              onClick={openFavorites}
            >
              <Heart size={22} filled={favorites.size > 0} />
            </button>
          </div>
          <div className="search-bar">
            <Search size={18} />
            <input
              type="text"
              className="search-bar__input"
              placeholder="상품명으로 검색"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setVisibleCount(PAGE_SIZE); }}
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
                    onClick={() => { setSort(option.key); setVisibleCount(PAGE_SIZE); }}
                  >
                    <span className="sort-bar__item-label">{option.label}</span>
                  </button>
                ))}
              </div>
            </div>
          );

          if (isSearching) {
            const sorted = sortProducts(filteredProducts, sort);
            const visible = sorted.slice(0, visibleCount);
            return (
              <>
                {sortRow}
                <div className="product-grid">
                  {visible.map((product) => (
                    <ProductCard
                      key={product.shareLink}
                      product={product}
                      onSelect={handleSelectProduct}
                      isFavorite={favorites.has(product.shareLink)}
                      onToggleFavorite={toggleFavorite}
                    />
                  ))}
                </div>
                {visible.length < sorted.length && (
                  <button
                    type="button"
                    className="load-more-button"
                    onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
                  >
                    더보기
                  </button>
                )}
              </>
            );
          }

          if (viewingFavorites) {
            const favoriteProducts = state.products.filter((p) => favorites.has(p.shareLink));
            const sortedFavorites = sortProducts(favoriteProducts, sort);
            const visibleFavorites = sortedFavorites.slice(0, visibleCount);
            return (
              <>
                <button type="button" className="back-to-home" onClick={closeFavorites}>
                  <ChevronLeft size={16} /> 홈
                </button>

                {favoriteProducts.length === 0 ? (
                  <p className="state-message">아직 찜한 상품이 없어요.</p>
                ) : (
                  <>
                    {sortRow}
                    <div className="product-grid">
                      {visibleFavorites.map((product) => (
                        <ProductCard
                          key={product.shareLink}
                          product={product}
                          onSelect={handleSelectProduct}
                          isFavorite
                          onToggleFavorite={toggleFavorite}
                        />
                      ))}
                    </div>
                    {visibleFavorites.length < sortedFavorites.length && (
                      <button
                        type="button"
                        className="load-more-button"
                        onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
                      >
                        더보기
                      </button>
                    )}
                  </>
                )}
              </>
            );
          }

          const groups = groupByCategory(filteredProducts);

          if (selectedCategory === null) {
            const productByLink = new Map(state.products.map((p) => [p.shareLink, p]));
            const recentProducts = recentIds
              .map((id) => productByLink.get(id))
              .filter((p): p is Product => p !== undefined);

            return (
              <>
                <TopDealsCarousel products={state.products} onSelect={handleSelectProduct} />

                <p className="daily-update-notice">매일 아침 10시, 더 많은 특가가 추가돼요</p>

                {recentProducts.length > 0 && (
                  <div className="category-shelf">
                    <div className="category-shelf__header">
                      <span className="category-shelf__title">최근 본 상품</span>
                    </div>
                    <div className="category-shelf__list">
                      {recentProducts.map((product) => (
                        <ProductCard
                          key={product.shareLink}
                          product={product}
                          onSelect={handleSelectProduct}
                          isFavorite={favorites.has(product.shareLink)}
                          onToggleFavorite={toggleFavorite}
                        />
                      ))}
                    </div>
                  </div>
                )}

                <div className="category-grid">
                  {groups.map((group) => (
                    <button
                      key={group.label}
                      type="button"
                      className="category-grid__item"
                      onClick={() => {
                        Analytics.click({ log_name: 'category_icon_click', category: group.label });
                        selectCategory(group.label);
                      }}
                    >
                      <span className="category-grid__emoji tf">
                        {CATEGORY_EMOJI[group.label] ?? DEFAULT_CATEGORY_EMOJI}
                      </span>
                      <span className="category-grid__label">{group.label}</span>
                    </button>
                  ))}
                </div>

                {groups.map((group) => (
                  <div className="category-shelf" key={group.label}>
                    <div className="category-shelf__header">
                      <span className="category-shelf__title">
                        <span className="tf">{CATEGORY_EMOJI[group.label] ?? DEFAULT_CATEGORY_EMOJI}</span>{' '}
                        {group.label} 특가 순위
                      </span>
                      <button
                        type="button"
                        className="category-shelf__more"
                        onClick={() => {
                          Analytics.click({ log_name: 'category_shelf_more_click', category: group.label });
                          selectCategory(group.label);
                        }}
                      >
                        전체보기
                      </button>
                    </div>
                    <div className="category-shelf__list">
                      {sortProducts(group.products, 'recommend')
                        .slice(0, SHELF_SIZE)
                        .map((product) => (
                          <ProductCard
                            key={product.shareLink}
                            product={product}
                            onSelect={handleSelectProduct}
                            isFavorite={favorites.has(product.shareLink)}
                            onToggleFavorite={toggleFavorite}
                          />
                        ))}
                    </div>
                  </div>
                ))}
              </>
            );
          }

          const activeGroup = groups.find((g) => g.label === selectedCategory) ?? groups[0];
          const sortedActive = sortProducts(activeGroup?.products ?? [], sort);
          const visibleActive = sortedActive.slice(0, visibleCount);
          return (
            <>
              <button type="button" className="back-to-home" onClick={() => setSelectedCategory(null)}>
                <ChevronLeft size={16} /> 홈
              </button>

              <nav className="category-tabs" aria-label="카테고리">
                {groups.map((group) => (
                  <button
                    key={group.label}
                    type="button"
                    className={
                      group.label === activeGroup?.label
                        ? 'category-tabs__item category-tabs__item--active'
                        : 'category-tabs__item'
                    }
                    onClick={() => {
                      Analytics.click({ log_name: 'category_tab_click', category: group.label });
                      selectCategory(group.label);
                    }}
                  >
                    {group.label}
                  </button>
                ))}
              </nav>

              {sortRow}

              <div className="product-grid">
                {visibleActive.map((product) => (
                  <ProductCard
                    key={product.shareLink}
                    product={product}
                    onSelect={handleSelectProduct}
                    isFavorite={favorites.has(product.shareLink)}
                    onToggleFavorite={toggleFavorite}
                  />
                ))}
              </div>
              {visibleActive.length < sortedActive.length && (
                <button
                  type="button"
                  className="load-more-button"
                  onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
                >
                  더보기
                </button>
              )}
            </>
          );
        })()}

        <p className="disclosure">
          이 앱은 토스쇼핑 파트너스 활동의 일환으로, 상품 구매 시 일정액의 수수료를 제공받습니다.
        </p>
      </div>

      {selectedProduct && (
        <PurchaseSheet product={selectedProduct} onClose={() => setSelectedProduct(null)} />
      )}
    </div>
  );
}

export default App;
