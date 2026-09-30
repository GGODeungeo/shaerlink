import type { Product } from './types';

const PACK_COUNT_SEGMENT = /^\d+(박스|개|팩|세트|입)$/;

/** 이름의 마지막 콤마 구획이 순수 개수 표기("2박스", "6개"...)면 그 앞부분을
 * 그룹 키로 쓴다 - 색상/사이즈처럼 진짜 다른 옵션은 마지막 구획이 이 패턴에
 * 안 걸려 건드리지 않는다. */
function baseKey(name: string): string {
  const segments = name.split(', ');
  const last = segments[segments.length - 1];
  if (segments.length > 1 && PACK_COUNT_SEGMENT.test(last)) {
    return segments.slice(0, -1).join(', ');
  }
  return name;
}

/** 같은 상품을 박스/개수 단위만 다르게 올린 리스팅(예: 루테인 골드
 * 2박스/3박스/6박스)을 한 장의 카드로 합친다. 그리드에는 최저가 옵션만
 * 대표로 보이고, 나머지는 그 카드의 `variants`에 실려 구매 시트에서
 * 고를 수 있다. */
export function groupPackVariants<T extends Product>(products: T[]): T[] {
  const groups = new Map<string, T[]>();
  const order: string[] = [];
  for (const p of products) {
    const key = baseKey(p.name);
    if (!groups.has(key)) {
      groups.set(key, []);
      order.push(key);
    }
    groups.get(key)!.push(p);
  }

  return order.map((key) => {
    const members = groups.get(key)!;
    if (members.length === 1) return members[0];
    const primary = members.reduce((best, p) => (p.price < best.price ? p : best));
    return { ...primary, variants: members };
  });
}
