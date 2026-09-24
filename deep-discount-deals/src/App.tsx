import { useEffect, useRef, useState } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import { ProductCard } from './ProductCard';
import { TopDealsCarousel } from './TopDealsCarousel';
import { PurchaseSheet } from './PurchaseSheet';
import { Bag, Heart, Search } from './components/icons';
import { useFavorites } from './useFavorites';
import { useRecentlyViewed } from './useRecentlyViewed';
import { usePaginatedProducts } from './usePaginatedProducts';
import { dedupeByImage } from './dedupeByImage';
import { dailyShuffle } from './dailyShuffle';
import { TodaysPickEvent } from './TodaysPickEvent';
import { PopularRanking } from './PopularRanking';
import { BannerAd } from './BannerAd';
import { PushOptInCard } from './PushOptInCard';
import type { Product, SortKey } from './types';
import './App.css';

const HOME_DATA_URL = 'https://shaerlink.vercel.app/api/products/home';
const PRODUCTS_BATCH_URL = 'https://shaerlink.vercel.app/api/products/batch';

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
const SHELF_POOL_SIZE = SHELF_SIZE * 2;

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

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'recommend', label: '추천순' },
  { key: 'discount', label: '할인율순' },
  { key: 'price', label: '낮은 가격순' },
];

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;

function sortProducts(products: Product[], sort: SortKey) {
  return [...products].sort((a, b) => {
    if (sort === 'discount') return b.discountRate - a.discountRate;
    if (sort === 'price') return a.price - b.price;
    return b.reviewCount - a.reviewCount;
  });
}

function App() {
  const [homeState, setHomeState] = useState<LoadState>({ status: 'loading' });
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>('recommend');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [viewingFavorites, setViewingFavorites] = useState(false);
  const [viewingEvent, setViewingEvent] = useState(false);
  const [viewingRecentlyViewed, setViewingRecentlyViewed] = useState(false);
  const [viewingRanking, setViewingRanking] = useState(false);
  const [favoriteItems, setFavoriteItems] = useState<Product[]>([]);
  const [recentItems, setRecentItems] = useState<Product[]>([]);
  const { favorites, toggleFavorite } = useFavorites();
  const { recentIds, recordView, removeView, clearAll } = useRecentlyViewed();

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  const isSearching = debouncedSearch.length > 0;
  const categoryState = usePaginatedProducts({ category: selectedCategory ?? undefined, sort });
  const searchState = usePaginatedProducts({ search: isSearching ? debouncedSearch : undefined, sort });

  const handleSelectProduct = (product: Product) => {
    recordView(product.shareLink);
    setSelectedProduct(product);
  };

  const selectCategory = (label: string) => {
    setSelectedCategory(label);
    setViewingFavorites(false);
    setViewingEvent(false);
    setViewingRecentlyViewed(false);
    setViewingRanking(false);
    setVisibleCount(PAGE_SIZE);
  };

  const openFavorites = () => {
    Analytics.click({ log_name: 'favorites_nav_click', favorite_count: favorites.size });
    setViewingFavorites(true);
    setViewingEvent(false);
    setViewingRecentlyViewed(false);
    setViewingRanking(false);
    setVisibleCount(PAGE_SIZE);
  };

  const openEvent = () => {
    setViewingEvent(true);
    setViewingFavorites(false);
    setViewingRecentlyViewed(false);
    setViewingRanking(false);
  };

  const openRecentlyViewedPage = () => {
    Analytics.click({ log_name: 'recently_viewed_nav_click', item_count: recentIds.length });
    setViewingRecentlyViewed(true);
    setViewingFavorites(false);
    setViewingEvent(false);
    setViewingRanking(false);
    setVisibleCount(PAGE_SIZE);
  };

  const openHome = () => {
    if (isSubView) window.history.back();
  };

  const openRanking = () => {
    Analytics.click({ log_name: 'ranking_teaser_click' });
    setViewingRanking(true);
    setViewingFavorites(false);
    setViewingEvent(false);
    setViewingRecentlyViewed(false);
    setVisibleCount(PAGE_SIZE);
  };

  const fetchJson = (url: string): Promise<Product[]> =>
    fetch(url).then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    });

  const fetchHomeProducts = () => {
    fetchJson(HOME_DATA_URL)
      .then((products) => setHomeState({ status: 'ready', products }))
      .catch(() => setHomeState({ status: 'error' }));
  };

  useEffect(fetchHomeProducts, []);

  // 찜 화면에 들어갈 때 스냅샷을 한 번만 가져온다. 화면 안에서 찜 해제는
  // favorites Set 변화를 렌더 시점에 바로 필터링해 즉시 반영하고, 여기서
  // 다시 fetch하지 않는다 - 안 그러면 매 토글마다 네트워크 왕복이 생겨
  // 카드가 사라지는 게 한 박자 늦게 보인다. (이 화면 안에서는 찜 추가가
  // 불가능하므로 - 항상 isFavorite=true로 렌더 - 스냅샷 이후의 축소만
  // 반영하면 충분하다.)
  useEffect(() => {
    if (!viewingFavorites) return;
    const ids = [...favorites];
    if (ids.length === 0) {
      setFavoriteItems([]);
      return;
    }
    fetch(`${PRODUCTS_BATCH_URL}?ids=${ids.map(encodeURIComponent).join(',')}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { items: Product[] }) => setFavoriteItems(data.items))
      .catch(() => setFavoriteItems([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewingFavorites]);

  // 최근본도 찜과 동일한 이유로 진입 시 스냅샷만 가져오고, 화면 안에서의
  // 개별 삭제/전체삭제는 아래 렌더에서 recentIds로 다시 필터링해 즉시
  // 반영한다.
  useEffect(() => {
    if (!viewingRecentlyViewed) return;
    if (recentIds.length === 0) {
      setRecentItems([]);
      return;
    }
    fetch(`${PRODUCTS_BATCH_URL}?ids=${recentIds.map(encodeURIComponent).join(',')}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { items: Product[] }) => {
        const byLink = new Map(data.items.map((p) => [p.shareLink, p]));
        setRecentItems(recentIds.map((id) => byLink.get(id)).filter((p): p is Product => p !== undefined));
      })
      .catch(() => setRecentItems([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewingRecentlyViewed]);

  // 주요 기능(앱 상세 화면 바로가기)이 intoss://hidden-deals?view=favorites 같은
  // 링크로 특정 화면을 바로 열 수 있게 한다.
  useEffect(() => {
    const view = new URLSearchParams(window.location.search).get('view');
    if (view === 'favorites') {
      Analytics.click({ log_name: 'deep_link_open', view });
      setViewingFavorites(true);
    } else if (view === 'event') {
      Analytics.click({ log_name: 'deep_link_open', view });
      setViewingEvent(true);
    } else if (view === 'recent') {
      Analytics.click({ log_name: 'deep_link_open', view });
      setViewingRecentlyViewed(true);
    } else if (view === 'ranking') {
      Analytics.click({ log_name: 'deep_link_open', view });
      setViewingRanking(true);
    }
  }, []);

  // 서브뷰(카테고리 상세/찜/이벤트/최근본)에 들어갈 때 history entry를 하나
  // 쌓아서, 플랫폼 자체 상단 뒤로가기 버튼 및 스와이프 제스처가 홈으로
  // 돌아오게 만든다 - 화면에 직접 그린 뒤로가기 버튼과 중복 노출되지 않도록
  // 자체 버튼은 두지 않는다.
  const isSubView =
    selectedCategory !== null || viewingFavorites || viewingEvent || viewingRecentlyViewed || viewingRanking;
  const wasSubView = useRef(false);

  useEffect(() => {
    if (isSubView && !wasSubView.current) {
      window.history.pushState({ hiddenDealsSubView: true }, '');
    }
    wasSubView.current = isSubView;
  }, [isSubView]);

  useEffect(() => {
    const goHome = () => {
      setSelectedCategory(null);
      setViewingFavorites(false);
      setViewingEvent(false);
      setViewingRecentlyViewed(false);
      setViewingRanking(false);
    };
    window.addEventListener('popstate', goHome);
    return () => window.removeEventListener('popstate', goHome);
  }, []);

  const retry = () => {
    setHomeState({ status: 'loading' });
    fetchHomeProducts();
  };

  return (
    <div className="canvas bg-canvas">
      <div className="page-container">
        <header className="page-header">
          <div className="page-header__row">
            <h1>반값 이상 특가</h1>
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

        {homeState.status === 'loading' && <p className="state-message">불러오는 중...</p>}

        {homeState.status === 'error' && (
          <div className="state-message">
            <p>상품을 불러오지 못했어요.</p>
            <button type="button" className="retry-button" onClick={retry}>
              다시 시도
            </button>
          </div>
        )}

        {homeState.status === 'ready' && (() => {
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
            if (searchState.status === 'loading') {
              return <p className="state-message">불러오는 중...</p>;
            }
            if (searchState.status === 'error') {
              return <p className="state-message">검색 결과를 불러오지 못했어요.</p>;
            }
            if (searchState.items.length === 0) {
              return <p className="state-message">검색 결과가 없어요.</p>;
            }
            return (
              <>
                {sortRow}
                <div className="product-grid">
                  {searchState.items.map((product) => (
                    <ProductCard
                      key={product.shareLink}
                      product={product}
                      onSelect={handleSelectProduct}
                      isFavorite={favorites.has(product.shareLink)}
                      onToggleFavorite={toggleFavorite}
                    />
                  ))}
                </div>
                {searchState.hasMore && (
                  <button type="button" className="load-more-button" onClick={searchState.loadMore}>
                    더보기
                  </button>
                )}
              </>
            );
          }

          if (viewingEvent) {
            return (
              <TodaysPickEvent
                products={homeState.products}
                onSelect={handleSelectProduct}
                favorites={favorites}
                onToggleFavorite={toggleFavorite}
              />
            );
          }

          if (viewingRecentlyViewed) {
            const recentProducts = recentItems.filter((p) => recentIds.includes(p.shareLink));
            const sortedRecent = sortProducts(recentProducts, sort);
            const visibleRecent = sortedRecent.slice(0, visibleCount);
            return (
              <>
                <div className="recently-viewed-page__header">
                  {recentProducts.length > 0 && (
                    <button
                      type="button"
                      className="recently-viewed-page__clear"
                      onClick={() => {
                        Analytics.click({ log_name: 'recently_viewed_clear_all_click', item_count: recentProducts.length });
                        clearAll();
                      }}
                    >
                      전체 삭제
                    </button>
                  )}
                </div>

                {recentProducts.length === 0 ? (
                  <p className="state-message">아직 본 상품이 없어요.</p>
                ) : (
                  <>
                    {sortRow}
                    <div className="product-grid">
                      {visibleRecent.map((product) => (
                        <ProductCard
                          key={product.shareLink}
                          product={product}
                          onSelect={handleSelectProduct}
                          isFavorite={favorites.has(product.shareLink)}
                          onToggleFavorite={toggleFavorite}
                          onRemove={removeView}
                        />
                      ))}
                    </div>
                    {visibleRecent.length < sortedRecent.length && (
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

          if (viewingRanking) {
            return (
              <PopularRanking
                products={homeState.products}
                onSelect={handleSelectProduct}
              />
            );
          }

          if (viewingFavorites) {
            const favoriteProducts = favoriteItems.filter((p) => favorites.has(p.shareLink));
            const sortedFavorites = sortProducts(favoriteProducts, sort);
            const visibleFavorites = sortedFavorites.slice(0, visibleCount);
            return (
              <>
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

          const groups = dailyShuffle(groupByCategory(homeState.products), 'category-order');

          if (selectedCategory === null) {
            const allTimeLowProducts = dailyShuffle(
              dedupeByImage(sortProducts(homeState.products.filter((p) => p.isAllTimeLow), 'recommend')).slice(
                0,
                SHELF_POOL_SIZE
              ),
              'all-time-low'
            ).slice(0, SHELF_SIZE);

            return (
              <>
                <TopDealsCarousel products={homeState.products} onSelect={handleSelectProduct} />

                <p className="daily-update-notice">매일 아침 10시, 더 많은 특가가 추가돼요</p>

                <PushOptInCard />

                <div className="payback-banner">
                  <span className="payback-banner__emoji tf">💸</span>
                  <span className="payback-banner__text">
                    <span className="payback-banner__title">5,000원 이상 구매하고 500원 페이백</span>
                    <span className="payback-banner__subtitle">지금 진행 중인 프로모션이에요, 페이백 받으세요</span>
                  </span>
                </div>

                {allTimeLowProducts.length > 0 && (
                  <div className="category-shelf">
                    <div className="category-shelf__header">
                      <span className="category-shelf__title">
                        <span className="tf">🔥</span> 역대 최저가 상품
                      </span>
                    </div>
                    <div className="category-shelf__list">
                      {allTimeLowProducts.map((product) => (
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
                  <button
                    type="button"
                    className="category-grid__item"
                    onClick={() => {
                      Analytics.click({ log_name: 'event_grid_tile_click' });
                      openEvent();
                    }}
                  >
                    <span className="category-grid__emoji tf">🎉</span>
                    <span className="category-grid__label">오늘의 특가 이벤트</span>
                  </button>
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
                      {dailyShuffle(
                        dedupeByImage(sortProducts(group.products, 'recommend')).slice(0, SHELF_POOL_SIZE),
                        `shelf-${group.label}`
                      )
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

                <BannerAd />
              </>
            );
          }

          const activeGroup = groups.find((g) => g.label === selectedCategory);

          if (categoryState.status === 'loading') {
            return (
              <>
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
                <p className="state-message">불러오는 중...</p>
              </>
            );
          }

          if (categoryState.status === 'error') {
            return <p className="state-message">카테고리 상품을 불러오지 못했어요.</p>;
          }

          if (categoryState.items.length === 0) {
            return <p className="state-message">지금은 조건에 맞는 상품이 없어요.</p>;
          }

          return (
            <>
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
                {categoryState.items.map((product) => (
                  <ProductCard
                    key={product.shareLink}
                    product={product}
                    onSelect={handleSelectProduct}
                    isFavorite={favorites.has(product.shareLink)}
                    onToggleFavorite={toggleFavorite}
                  />
                ))}
              </div>
              {categoryState.hasMore && (
                <button type="button" className="load-more-button" onClick={categoryState.loadMore}>
                  더보기
                </button>
              )}
            </>
          );
        })()}

        <p className="disclosure">
          이 앱은 토스쇼핑 파트너스 활동의 일환으로,
          <br />
          상품 구매 시 일정액의 수수료를 제공받습니다.
        </p>
      </div>

      <div className="quick-nav-pill">
        <button type="button" className="quick-nav-pill__item" onClick={openHome}>
          <span className="tf quick-nav-pill__icon">🏠</span>
          <span className="quick-nav-pill__label">홈</span>
        </button>
        <button type="button" className="quick-nav-pill__item" onClick={openRanking}>
          <span className="tf quick-nav-pill__icon">👑</span>
          <span className="quick-nav-pill__label">랭킹</span>
        </button>
        <button
          type="button"
          className="quick-nav-pill__item"
          data-active={favorites.size > 0}
          onClick={openFavorites}
        >
          <Heart size={18} filled={favorites.size > 0} />
          <span className="quick-nav-pill__label">찜</span>
          {favorites.size > 0 && <span className="quick-nav-pill__badge">{favorites.size}</span>}
        </button>
        {recentIds.length > 0 && (
          <button type="button" className="quick-nav-pill__item" onClick={openRecentlyViewedPage}>
            <Bag size={18} />
            <span className="quick-nav-pill__label">최근본</span>
          </button>
        )}
      </div>

      {selectedProduct && (
        <PurchaseSheet product={selectedProduct} onClose={() => setSelectedProduct(null)} />
      )}
    </div>
  );
}

export default App;
