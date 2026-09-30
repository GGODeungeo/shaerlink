import { ProductCard } from './ProductCard';
import { dedupeByImage } from './dedupeByImage';
import type { Product } from './types';

const AUTUMN_CATEGORIES = ['패션의류잡화', '식품'];
const AUTUMN_DEALS_END = new Date('2026-10-31T00:00:00+09:00');

export const isAutumnDealsActive = () => new Date() < AUTUMN_DEALS_END;

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
  const autumnProducts = dedupeByImage(
    products
      .filter((p) => AUTUMN_CATEGORIES.includes(p.category))
      .sort((a, b) => b.discountRate - a.discountRate)
  );

  return (
    <div className="event-page">
      <h2 className="event-page__title">🍂 가을특가</h2>
      <p className="event-page__subtitle">가을에 딱 맞는 옷과 식품 특가만 모았어요</p>
      <p className="event-page__subtitle">10월 30일까지 진행돼요</p>

      {autumnProducts.length === 0 ? (
        <p className="state-message">지금은 보여드릴 상품이 없어요.</p>
      ) : (
        <div className="product-grid">
          {autumnProducts.map((product) => (
            <ProductCard
              key={product.shareLink}
              product={product}
              onSelect={onSelect}
              isFavorite={favorites.has(product.shareLink)}
              onToggleFavorite={onToggleFavorite}
            />
          ))}
        </div>
      )}
    </div>
  );
}
