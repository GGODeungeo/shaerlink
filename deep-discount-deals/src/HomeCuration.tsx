import { Analytics } from '@apps-in-toss/web-framework';
import { isAutumnDealsActive } from './AutumnDealsEvent';
import { ChevronRight } from './components/icons';
import { dailyShuffle } from './dailyShuffle';
import { dedupeByImage } from './dedupeByImage';
import { groupProductVariants } from './groupProductVariants';
import { rankedProducts } from './PopularRanking';
import { ProductCard } from './ProductCard';
import type { Product } from './types';

const TODAY_CATEGORY_COUNT = 3;
const TODAY_CATEGORY_MIN = 6;
const SHELF_SIZE = 6;

/** 오늘의 카테고리 한 줄 소개 - 없는 카테고리는 기본 문구. */
const CATEGORY_DESC: Record<string, string> = {
  '식품': '장보기 전에 먼저 보면 좋은 먹거리',
  '가구/홈데코': '집 안 분위기를 바꾸는 작은 가구',
  '가전/디지털': '오래 쓸 기기를 좋은 가격에',
  '뷰티': '매일 쓰는 화장품을 넉넉하게',
  '생활용품': '떨어지기 전에 쟁여 두는 생필품',
  '스포츠/레져': '선선한 날 밖으로 나갈 준비',
  '자동차용품': '차 안을 정돈하는 실속템',
  '주방용품': '요리가 즐거워지는 주방 도구',
  '완구/취미': '아이와 함께, 혼자서도 즐겁게',
  '반려/애완용품': '반려동물과 함께하는 매일',
  '패션의류잡화': '계절이 바뀔 때 필요한 옷과 잡화',
  '문구/오피스': '책상 위를 채우는 문구',
  '출산/유아동': '아이 키우는 집에 필요한 것들',
};

type Group = { label: string; products: Product[] };

function SectionHeader({ overline, title, desc, onMore }: { overline: string; title: string; desc: string; onMore?: () => void }) {
  return (
    <div className="curation__header">
      <div>
        <p className="curation__overline">{overline}</p>
        <h3 className="curation__title">{title}</h3>
        <p className="curation__desc">{desc}</p>
      </div>
      {onMore && (
        <button type="button" className="curation__more" onClick={onMore}>
          전체보기
          <ChevronRight />
        </button>
      )}
    </div>
  );
}

export function HomeCuration({
  groups,
  products,
  onSelect,
  favorites,
  onToggleFavorite,
  onOpenCategory,
  onOpenRanking,
  onOpenAutumn,
}: {
  groups: Group[];
  products: Product[];
  onSelect: (product: Product) => void;
  favorites: Set<string>;
  onToggleFavorite: (shareLink: string) => void;
  onOpenCategory: (label: string) => void;
  onOpenRanking: () => void;
  onOpenAutumn: () => void;
}) {
  // groups는 이미 날짜별로 섞인 순서라, 상품이 충분한 앞쪽 3개가 오늘의 카테고리.
  const todays = groups
    .filter((g) => g.products.length >= TODAY_CATEGORY_MIN && CATEGORY_DESC[g.label])
    .slice(0, TODAY_CATEGORY_COUNT);
  const topRanked = rankedProducts(products).slice(0, 3);
  const autumnPreview = isAutumnDealsActive()
    ? groupProductVariants(dedupeByImage(products.filter((p) => p.isAutumn))).slice(0, 3)
    : [];

  const categoryBlock = (g: Group) => (
    <section className="curation" key={g.label}>
      <SectionHeader
        overline="오늘의 카테고리"
        title={g.label}
        desc={CATEGORY_DESC[g.label]}
        onMore={() => {
          Analytics.click({ log_name: 'today_category_more_click', category: g.label });
          onOpenCategory(g.label);
        }}
      />
      <div className="category-shelf__list">
        {dailyShuffle(groupProductVariants(dedupeByImage(g.products)), `today-${g.label}`)
          .slice(0, SHELF_SIZE)
          .map((product) => (
            <ProductCard
              key={product.shareLink}
              product={product}
              onSelect={onSelect}
              isFavorite={favorites.has(product.shareLink)}
              onToggleFavorite={onToggleFavorite}
            />
          ))}
      </div>
    </section>
  );

  const rankingBlock = topRanked.length > 0 && (
    <section className="curation" key="ranking">
      <SectionHeader overline="랭킹" title="많이 산 특가 TOP 3" desc="구매 후기가 가장 많은 상품이에요" />
      <div className="curation-card">
        {topRanked.map((product, i) => {
          const [title] = product.name.split(', ');
          return (
            <button key={product.shareLink} type="button" className="ranking-row" onClick={() => onSelect(product)}>
              <span className="ranking-row__rank" data-top="true">{i + 1}</span>
              <img src={product.imageUrl} alt={title} className="ranking-row__image" loading="lazy" />
              <span className="ranking-row__info">
                <span className="ranking-row__title">{title}</span>
                <span className="ranking-row__price">
                  <span className="ranking-row__rate">{product.discountRate}%</span>
                  {product.price.toLocaleString()}원
                </span>
              </span>
            </button>
          );
        })}
        <button
          type="button"
          className="curation-card__cta"
          onClick={() => {
            Analytics.click({ log_name: 'home_ranking_more_click' });
            onOpenRanking();
          }}
        >
          30위까지 전체 순위 보기
          <ChevronRight />
        </button>
      </div>
    </section>
  );

  const autumnBlock = autumnPreview.length >= 3 && (
    <section className="curation" key="autumn">
      <button
        type="button"
        className="autumn-teaser"
        onClick={() => {
          Analytics.click({ log_name: 'home_autumn_teaser_click' });
          onOpenAutumn();
        }}
      >
        <span className="autumn-teaser__text">
          <span className="autumn-hero__overline">AUTUMN EDIT</span>
          <span className="autumn-teaser__title">가을을 고르는 시간</span>
          <span className="autumn-teaser__desc">니트부터 햇과일까지, 제철만 모았어요</span>
        </span>
        <span className="autumn-teaser__images">
          {autumnPreview.map((p) => (
            <img key={p.shareLink} src={p.imageUrl} alt="" loading="lazy" />
          ))}
        </span>
      </button>
    </section>
  );

  // 상품 줄과 안내 블록을 번갈아 배치해 끝없는 나열처럼 보이지 않게 한다.
  return (
    <>
      {todays[0] && categoryBlock(todays[0])}
      {rankingBlock}
      {todays[1] && categoryBlock(todays[1])}
      {autumnBlock}
      {todays[2] && categoryBlock(todays[2])}
    </>
  );
}
