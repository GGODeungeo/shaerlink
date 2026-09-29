import { ProductCard } from './ProductCard';
import { dedupeByImage } from './dedupeByImage';
import type { Product } from './types';

const AUTUMN_CATEGORIES = ['패션의류잡화', '식품'];
const EVENT_SIZE = 20;

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
  ).slice(0, EVENT_SIZE);

  return (
    <div className="event-page">
      <h2 className="event-page__title">🍂 가을특가</h2>
      <p className="event-page__subtitle">가을에 딱 맞는 옷과 식품 특가만 모았어요</p>

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
