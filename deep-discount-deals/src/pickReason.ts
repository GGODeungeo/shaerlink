import { reviewCountLabel } from './reviewCount';
import { savingsAmount } from './savings';
import type { Product } from './types';

/** Short honest reason text derived only from real product fields - no
 * fabricated review quotes or claims we can't back with data. */
export function pickReason(product: Product): string {
  if (product.isAllTimeLow) return '역대 최저가예요';
  if (product.discountRate >= 90) return `할인율이 무려 ${product.discountRate}%예요`;
  if (product.reviewCount >= 10000) return `${reviewCountLabel(product.reviewCount)} 넘게 팔렸어요`;
  const savings = savingsAmount(product);
  if (savings >= 20000) return `${savings.toLocaleString()}원이나 아낄 수 있어요`;
  return `${product.discountRate}% 할인 중이에요`;
}
