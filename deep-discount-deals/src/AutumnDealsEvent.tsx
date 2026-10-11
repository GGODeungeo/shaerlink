import { useRef } from 'react';
import { Analytics } from '@apps-in-toss/web-framework';
import { Heart } from './components/icons';
import { dedupeByImage } from './dedupeByImage';
import { groupProductVariants } from './groupProductVariants';
import type { Product } from './types';

const AUTUMN_DEALS_END = new Date('2026-10-31T00:00:00+09:00');
const PER_SECTION = 8;

export const isAutumnDealsActive = () => new Date() < AUTUMN_DEALS_END;

/** 서버(fetch_home_products)가 상품마다 붙이는 autumnTheme 순서대로, 옷과
 * 먹거리가 번갈아 나오게 섹션을 짠다. */
const SECTIONS = [
  { theme: 'outer', label: '아우터·니트', title: '선선한 날의 아우터와 니트', desc: '아침저녁 기온 차에 걸치기 좋은 한 벌' },
  { theme: 'fruit', label: '제철 과일', title: '지금이 가장 맛있는 과일', desc: '햇사과와 극조생 감귤이 나오는 때예요' },
  { theme: 'cozy', label: '포근한 소품', title: '집에서 보내는 포근한 저녁', desc: '잠옷과 머플러로 채우는 따뜻함' },
  { theme: 'table', label: '가을 별미', title: '가을 식탁의 별미', desc: '햇밤, 고구마, 꽃게까지 제철 그대로' },
] as const;

function AutumnCard({
  product,
  onSelect,
  isFavorite,
  onToggleFavorite,
}: {
  product: Product;
  onSelect: (product: Product) => void;
  isFavorite: boolean;
  onToggleFavorite: (shareLink: string) => void;
}) {
  const [title] = product.name.split(', ');

  const open = () => {
    Analytics.click({
      log_name: 'product_card_click',
      product_name: product.name,
      product_category: product.category,
      discount_rate: product.discountRate,
      price: product.price,
    });
    onSelect(product);
  };

  const toggleFavorite = (e: React.MouseEvent) => {
    e.stopPropagation();
    Analytics.click({ log_name: 'favorite_toggle_click', product_name: product.name, favorited: !isFavorite });
    onToggleFavorite(product.shareLink);
  };

  return (
    <div
      className="autumn-card"
      role="button"
      tabIndex={0}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          open();
        }
      }}
    >
      <div className="autumn-card__image-wrap">
        <img src={product.imageUrl} alt={title} className="autumn-card__image" loading="lazy" decoding="async" />
        <button
          type="button"
          className="autumn-card__favorite"
          data-active={isFavorite}
          aria-label={isFavorite ? '찜 해제하기' : '찜하기'}
          onClick={toggleFavorite}
        >
          <Heart size={18} filled={isFavorite} />
        </button>
      </div>
      <div className="autumn-card__title">{title}</div>
      <div className="autumn-card__price">
        <span className="autumn-card__rate">{product.discountRate}%</span>
        {product.price.toLocaleString()}원
      </div>
    </div>
  );
}

export function AutumnDealsEvent({
  products,
  onSelect,
  favorites,
  onToggleFavorite,
}: {
  products: Product[];
  onSelect: (product: Product) => void;
  favorites: Set<string>;
  onToggleFavorite: (shareLink: string) => void;
}) {
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  const autumnProducts = groupProductVariants(
    dedupeByImage(products.filter((p) => p.isAutumn).sort((a, b) => b.discountRate - a.discountRate))
  );
  // 한두 개뿐인 테마는 섹션이 휑해 보여서 뺀다.
  const sections = SECTIONS.map((s) => ({
    ...s,
    items: autumnProducts.filter((p) => p.autumnTheme === s.theme).slice(0, PER_SECTION),
  })).filter((s) => s.items.length >= 3);

  const jumpTo = (theme: string) => {
    Analytics.click({ log_name: 'autumn_theme_jump_click', theme });
    sectionRefs.current[theme]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="autumn">
      <header className="autumn-hero">
        <p className="autumn-hero__overline">AUTUMN EDIT · 10월 30일까지</p>
        <h2 className="autumn-hero__title">가을을 고르는 시간</h2>
        <p className="autumn-hero__desc">제철 과일부터 니트까지, 지금 좋은 가격의 가을만 골라 담았어요</p>
        {sections.length > 1 && (
          <nav className="autumn-hero__index" aria-label="가을특가 테마">
            {sections.map((s) => (
              <button key={s.theme} type="button" className="autumn-hero__chip" onClick={() => jumpTo(s.theme)}>
                {s.label}
              </button>
            ))}
          </nav>
        )}
      </header>

      {sections.length === 0 ? (
        <p className="state-message">지금은 보여드릴 상품이 없어요.</p>
      ) : (
        sections.map((s, i) => (
          <section
            key={s.theme}
            className="autumn-section"
            ref={(el) => {
              sectionRefs.current[s.theme] = el;
            }}
          >
            <p className="autumn-section__overline">
              {String(i + 1).padStart(2, '0')} · {s.label}
            </p>
            <h3 className="autumn-section__title">{s.title}</h3>
            <p className="autumn-section__desc">{s.desc}</p>
            <div className="autumn-section__list">
              {s.items.map((product) => (
                <AutumnCard
                  key={product.shareLink}
                  product={product}
                  onSelect={onSelect}
                  isFavorite={favorites.has(product.shareLink)}
                  onToggleFavorite={onToggleFavorite}
                />
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
