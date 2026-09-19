import { getAnonymousKey } from '@apps-in-toss/web-framework';
import type { Product } from './types';

const LINK_API_URL = 'https://shaerlink.vercel.app/api/link';

let anonKeyPromise: Promise<string | null> | null = null;

async function resolveAnonKey(): Promise<string | null> {
  try {
    const result = await getAnonymousKey();
    return result && typeof result === 'object' && result.type === 'HASH' ? result.hash : null;
  } catch {
    return null;
  }
}

function getAnonKey(): Promise<string | null> {
  if (!anonKeyPromise) anonKeyPromise = resolveAnonKey();
  return anonKeyPromise;
}

/** Issues a fresh sharelink tagged with this user's anon key, so a later
 * purchase can be attributed to them for the buy-and-get-rewarded
 * promotion. Falls back to the pre-batched static link on any failure
 * (missing tacaItemId, network error, unsupported SDK) so purchases never
 * break because of this. */
export async function getTrackedPurchaseUrl(product: Product): Promise<string> {
  if (!product.tacaItemId) return product.shareLink;

  const anonKey = await getAnonKey();
  if (!anonKey) return product.shareLink;

  try {
    const response = await fetch(LINK_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-internal-token': import.meta.env.VITE_LINK_API_TOKEN,
      },
      body: JSON.stringify({ tacaItemId: product.tacaItemId, anonKey }),
    });
    if (!response.ok) return product.shareLink;
    const data = await response.json();
    return data.url ?? product.shareLink;
  } catch {
    return product.shareLink;
  }
}
