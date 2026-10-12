import { useEffect, useState } from 'react';
import { Analytics, Environment } from '@apps-in-toss/web-framework';
import { rankedProducts } from './PopularRanking';
import { canAskDealPush, requestDealPush } from './PushOptInCard';
import { savingsAmount } from './savings';
import type { Product } from './types';

const SLIDE_MS = 3300;
const SLIDE_COUNT = 3;

/** 토스 혜택탭(프로모션)에서 들어왔는지. 진입 스킴 URL의 referrer로 판단하고,
 * 로컬 미리보기용으로 페이지 주소의 ?referrer=도 본다. */
export function isBenefitTabEntry(): boolean {
  const fromUrl = (url: string) => {
    try {
      return new URL(url).searchParams.get('referrer');
    } catch {
      return null;
    }
  };
  let initial: string | null = null;
  try {
    initial = fromUrl(Environment.initialURL);
  } catch {
    // SDK 밖(브라우저)에서는 Environment가 없을 수 있다
  }
  return (initial ?? fromUrl(location.href)) === 'benefit_tab';
}

/** 혜택탭 프로모션으로 들어온 사람에게만 홈 맨 위에 보여주는 첫 화면.
 * 덮는 창이 아니라 페이지 일부다(진입 직후 시트는 검수 반려 사유). 많이 산
 * 특가 3개를 스토리처럼 약 3초씩 넘겨 첫 10초 안에 이 앱이 뭔지 보여주고,
 * 다시 올 이유(저녁 7시 알림)는 사용자가 직접 누를 때만 요청한다. */
export function BenefitWelcome({ products, onSelect }: { products: Product[]; onSelect: (p: Product) => void }) {
  const picks = rankedProducts(products).slice(0, SLIDE_COUNT);
  const [index, setIndex] = useState(0);
  const [canAskPush, setCanAskPush] = useState(canAskDealPush);

  useEffect(() => {
    Analytics.screen({ log_name: 'benefit_welcome_view' });
  }, []);

  useEffect(() => {
    if (picks.length <= 1) return;
    const timer = setInterval(() => setIndex((i) => (i + 1) % picks.length), SLIDE_MS);
    return () => clearInterval(timer);
  }, [picks.length]);

  const product = picks[index];
  if (!product) return null;

  const [title] = product.name.split(', ');
  const totalSavings = picks.reduce((sum, p) => sum + savingsAmount(p), 0);

  return (
    <section className="welcome" aria-label="많이 산 특가">
      <p className="welcome__greeting">반가워요! 반값 이상 특가만 모은 곳이에요</p>
      <button
        type="button"
        className="welcome-story"
        onClick={() => {
          Analytics.click({ log_name: 'benefit_story_click', rank: index + 1, product_name: product.name });
          onSelect(product);
        }}
      >
        <img key={product.shareLink} src={product.imageUrl} alt={title} className="welcome-story__image" />
        <span className="welcome-story__scrim" />
        <span className="welcome-story__bars" aria-hidden="true">
          {picks.map((p, i) => (
            <span key={p.shareLink} className="welcome-story__bar">
              <span
                key={i === index ? `active-${index}` : p.shareLink}
                className="welcome-story__fill"
                data-state={i < index ? 'done' : i === index ? 'active' : 'todo'}
                style={{ animationDuration: `${SLIDE_MS}ms` }}
              />
            </span>
          ))}
        </span>
        <span className="welcome-story__text">
          <span className="welcome-story__rank">많이 산 특가 {index + 1}위</span>
          <span className="welcome-story__title">{title}</span>
          <span className="welcome-story__price">
            <span className="welcome-story__rate">{product.discountRate}%</span>
            {product.price.toLocaleString()}원
          </span>
          <span className="welcome-story__savings">{savingsAmount(product).toLocaleString()}원 아껴요</span>
        </span>
      </button>
      <p className="welcome__summary">
        이 {picks.length}개만 사도 <strong>{totalSavings.toLocaleString()}원</strong> 아껴요
      </p>
      {canAskPush && (
        <button
          type="button"
          className="welcome__push"
          onClick={() => requestDealPush('benefit_welcome', () => setCanAskPush(false))}
        >
          <span className="welcome__push-title">매일 저녁 7시, 새 특가 알림 받기</span>
          <span className="welcome__push-desc">놓치기 쉬운 반값 특가를 먼저 알려드려요</span>
        </button>
      )}
    </section>
  );
}
