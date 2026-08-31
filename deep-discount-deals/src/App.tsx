import { useEffect, useState } from 'react';
import { CategoryNav } from './CategoryNav';
import { CategoryPage } from './CategoryPage';
import { Hero } from './Hero';
import type { Product } from './types';
import './App.css';

const DATA_URL =
  'https://raw.githubusercontent.com/GGODeungeo/shaerlink/main/app-data/products.json';

function groupByCategory(products: Product[]) {
  const byCategory = new Map<string, Product[]>();
  for (const product of products) {
    const list = byCategory.get(product.category) ?? [];
    list.push(product);
    byCategory.set(product.category, list);
  }
  return [...byCategory.entries()]
    .map(([category, items]) => ({ label: category, products: items }))
    .sort((a, b) => b.products.length - a.products.length);
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'ready'; products: Product[] };

type Screen = { name: 'home' } | { name: 'category'; label: string };

function App() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [screen, setScreen] = useState<Screen>({ name: 'home' });

  const fetchProducts = () => {
    fetch(DATA_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((products: Product[]) => setState({ status: 'ready', products }))
      .catch(() => setState({ status: 'error' }));
  };

  useEffect(fetchProducts, []);

  const retry = () => {
    setState({ status: 'loading' });
    fetchProducts();
  };

  if (state.status === 'ready' && screen.name === 'category') {
    const group = groupByCategory(state.products).find((g) => g.label === screen.label);
    return (
      <div className="canvas bg-canvas">
        <div className="page-container">
          <CategoryPage
            label={screen.label}
            products={group?.products ?? []}
            onBack={() => setScreen({ name: 'home' })}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="canvas bg-canvas">
      <div className="page-container">
        <header className="page-header">
          <h1>반값 이상 특가</h1>
        </header>

        {state.status === 'loading' && <p className="state-message">불러오는 중...</p>}

        {state.status === 'error' && (
          <div className="state-message">
            <p>상품을 불러오지 못했어요.</p>
            <button type="button" className="retry-button" onClick={retry}>
              다시 시도
            </button>
          </div>
        )}

        {state.status === 'ready' && (() => {
          const groups = groupByCategory(state.products);
          const topProduct = state.products.reduce((best, p) =>
            p.discountRate > best.discountRate ? p : best
          );
          return (
            <>
              <Hero product={topProduct} />
              <CategoryNav
                categories={groups.map((g) => g.label)}
                onSelect={(label) => setScreen({ name: 'category', label })}
              />
            </>
          );
        })()}
      </div>
    </div>
  );
}

export default App;
