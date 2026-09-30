import { useEffect, useRef } from 'react';

/** Invisible sentinel that fires onIntersect when scrolled near it, instead
 * of a "더보기" button the user has to tap. Mount it only while hasMore is
 * true - it unmounts (and stops observing) on its own once the parent list
 * runs out of pages. */
export function InfiniteScrollTrigger({ onIntersect }: { onIntersect: () => void }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const onIntersectRef = useRef(onIntersect);

  useEffect(() => {
    onIntersectRef.current = onIntersect;
  });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) onIntersectRef.current();
      },
      { rootMargin: '600px' }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return <div ref={ref} aria-hidden="true" />;
}
