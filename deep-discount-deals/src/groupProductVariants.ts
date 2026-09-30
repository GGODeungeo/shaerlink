import type { Product } from './types';

/** 같은 상품을 색상·용량·수량·사이즈 등 옵션만 다르게 올린 리스팅(이름의
 * 첫 콤마 구획, 즉 제목이 동일한 것들)을 한 장의 카드로 합친다. 그리드에는
 * 최저가 옵션만 대표로 보이고, 나머지는 그 카드의 `variants`에 실려
 * 구매 시트에서 고를 수 있다. */
export function groupProductVariants<T extends Product>(products: T[]): T[] {
  const groups = new Map<string, T[]>();
  const order: string[] = [];
  for (const p of products) {
    const title = p.name.split(', ')[0];
    if (!groups.has(title)) {
      groups.set(title, []);
      order.push(title);
    }
    groups.get(title)!.push(p);
  }

  return order.map((title) => {
    const members = groups.get(title)!;
    if (members.length === 1) return members[0];
    const primary = members.reduce((best, p) => (p.price < best.price ? p : best));
    return { ...primary, variants: members };
  });
}
