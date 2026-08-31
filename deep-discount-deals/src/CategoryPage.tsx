import { ChevronLeft } from './components/icons';
import { ProductCard } from './ProductCard';
import type { Product } from './types';

export function CategoryPage({
  label,
  products,
  onBack,
}: {
  label: string;
  products: Product[];
  onBack: () => void;
}) {
  return (
    <div className="category-page">
      <header className="category-page__header">
        <button type="button" className="category-page__back" onClick={onBack} aria-label="뒤로가기">
          <ChevronLeft size={20} />
        </button>
        <h1 className="category-page__title">{label}</h1>
      </header>
      <div className="product-grid">
        {products.map((product) => (
          <ProductCard key={product.shareLink} product={product} />
        ))}
      </div>
    </div>
  );
}
