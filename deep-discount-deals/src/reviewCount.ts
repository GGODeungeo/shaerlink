export function reviewCountLabel(count: number): string | null {
  if (count <= 0) return null;
  if (count >= 10000) return `리뷰 ${(count / 10000).toFixed(1).replace(/\.0$/, '')}만개`;
  return `리뷰 ${count.toLocaleString()}개`;
}
