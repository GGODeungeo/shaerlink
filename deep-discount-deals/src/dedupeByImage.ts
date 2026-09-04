/**
 * 같은 판매자가 이름만 다르게(색상/디자인 옵션) 올린 상품이 같은 이미지를
 * 재사용하는 경우가 많아, 순위/추천 목록에서 사실상 같은 상품이 여러 칸을
 * 차지해 보인다. imageUrl 기준으로 첫 등장만 남긴다.
 */
export function dedupeByImage<T extends { imageUrl: string }>(products: T[]): T[] {
  const seen = new Set<string>();
  return products.filter((p) => {
    if (seen.has(p.imageUrl)) return false;
    seen.add(p.imageUrl);
    return true;
  });
}
