import { useEffect, useState } from 'react';
import type { Product, SortKey } from './types';

const PRODUCTS_URL = 'https://shaerlink.vercel.app/api/products';
const DEFAULT_LIMIT = 20;

type Status = 'loading' | 'error' | 'ready';

type PageState = {
  items: Product[];
  nextCursor: string | null;
  status: Status;
};

function buildUrl(params: { category?: string; search?: string; sort: SortKey; cursor?: string | null }) {
  const qs = new URLSearchParams({ sort: params.sort, limit: String(DEFAULT_LIMIT) });
  if (params.category) qs.set('category', params.category);
  if (params.search) qs.set('search', params.search);
  if (params.cursor) qs.set('cursor', params.cursor);
  return `${PRODUCTS_URL}?${qs}`;
}

/** category/search 중 하나로 서버에서 커서 페이지네이션된 상품 목록을
 * 가져온다. category/search/sort 중 하나라도 바뀌면 1페이지부터 새로
 * 가져오고, 둘 다 없으면(undefined) fetch하지 않는다 - 카테고리를 아직 안
 * 고른 홈 화면에서 이 훅을 미리 호출해도 조용히 아무 것도 안 한다. */
export function usePaginatedProducts(params: { category?: string; search?: string; sort: SortKey }) {
  const { category, search, sort } = params;
  const [state, setState] = useState<PageState>({ items: [], nextCursor: null, status: 'loading' });

  useEffect(() => {
    if (!category && !search) return;
    setState({ items: [], nextCursor: null, status: 'loading' });
    fetch(buildUrl({ category, search, sort }))
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { items: Product[]; nextCursor: string | null }) =>
        setState({ items: data.items, nextCursor: data.nextCursor, status: 'ready' })
      )
      .catch(() => setState({ items: [], nextCursor: null, status: 'error' }));
  }, [category, search, sort]);

  const loadMore = () => {
    if (!state.nextCursor) return;
    fetch(buildUrl({ category, search, sort, cursor: state.nextCursor }))
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: { items: Product[]; nextCursor: string | null }) =>
        setState((prev) => ({
          items: [...prev.items, ...data.items],
          nextCursor: data.nextCursor,
          status: 'ready',
        }))
      )
      .catch(() => {});
  };

  return { items: state.items, status: state.status, hasMore: state.nextCursor !== null, loadMore };
}
