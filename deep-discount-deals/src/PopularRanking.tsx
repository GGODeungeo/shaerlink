import { dedupeByImage } from './dedupeByImage';
import { groupProductVariants } from './groupProductVariants';
import { reviewCountLabel } from './reviewCount';
import type { Product } from './types';

const RANKING_SIZE = 30;

/** 랭킹 = 리뷰(구매 후기) 많은 순. 홈 캐러셀이 이 목록과 겹치지 않게 같은
 * 계산을 공유한다. */
export function rankedProducts(products: Product[]): Product[] {
  return groupProductVariants(
    dedupeByImage([...products].sort((a, b) => b.reviewCount - a.reviewCount))
  ).slice(0, RANKING_SIZE);
}

export function PopularRanking({
  products,
  onSelect,
}: {
  products: Product[];
  onSelect: (product: Product) => void;
}) {
  const ranked = rankedProducts(products);

  return (
    <div className="ranking">
      <header className="ranking__header">
        <p className="ranking__overline">RANKING</p>
        <h2 className="ranking__title">많이 산 특가 순위</h2>
        <p className="ranking__desc">구매 후기가 많은 순서로 30개를 골랐어요</p>
      </header>

      {ranked.length === 0 ? (
        <p className="state-message">지금은 보여드릴 상품이 없어요.</p>
      ) : (
        <ol className="ranking__list">
          {ranked.map((product, i) => {
            const [title] = product.name.split(', ');
            const reviews = reviewCountLabel(product.reviewCount);
            return (
              <li key={product.shareLink}>
                <button type="button" className="ranking-row" onClick={() => onSelect(product)}>
                  <span className="ranking-row__rank" data-top={i < 3}>
                    {i + 1}
                  </span>
                  <img src={product.imageUrl} alt={title} className="ranking-row__image" loading="lazy" />
                  <span className="ranking-row__info">
                    <span className="ranking-row__title">{title}</span>
                    <span className="ranking-row__price">
                      <span className="ranking-row__rate">{product.discountRate}%</span>
                      {product.price.toLocaleString()}원
                    </span>
                    {reviews && <span className="ranking-row__reviews">{reviews}</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
