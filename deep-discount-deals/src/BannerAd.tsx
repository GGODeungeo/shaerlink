import { useEffect, useRef, useState } from 'react';
import { TossAds } from '@apps-in-toss/web-framework';

// 개발 중에는 반드시 테스트 광고 ID를 쓴다 - 실 광고 ID로 테스트하면 정책 위반으로 제재될 수 있다.
const AD_GROUP_ID = import.meta.env.DEV ? 'ait-ad-test-banner-id' : 'ait.v2.live.5d4e0c468979422d';

export function BannerAd() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    if (!TossAds.initialize.isSupported()) return;
    TossAds.initialize({
      callbacks: {
        onInitialized: () => setIsInitialized(true),
        onInitializationFailed: () => {},
      },
    });
  }, []);

  useEffect(() => {
    if (!isInitialized || !containerRef.current || !TossAds.attachBanner.isSupported()) return;
    const attached = TossAds.attachBanner(AD_GROUP_ID, containerRef.current, {
      theme: 'auto',
      tone: 'blackAndWhite',
      variant: 'expanded',
    });
    return () => attached?.destroy();
  }, [isInitialized]);

  return <div ref={containerRef} className="banner-ad" />;
}
