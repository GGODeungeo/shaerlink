import { useEffect, useState } from 'react';
import { ProductCard } from './ProductCard';
import type { Product } from './types';
import './App.css';

const DATA_URL =
  'https://raw.githubusercontent.com/GGODeungeo/shaerlink/main/app-data/products.json';

type LoadState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'ready'; products: Product[] };

function App() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });

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

  return (
    <div className="canvas bg-canvas">
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

      {state.status === 'ready' && (
        <div className="product-grid">
          {state.products.map((product) => (
            <ProductCard key={product.shareLink} product={product} />
          ))}
        </div>
      )}
    </div>
  );
}

export default App;
