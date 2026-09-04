/**
 * API가 할인 전 원가를 별도로 안 줘서 displayPrice/discountRate로 역산한다.
 * 판매자가 올린 원가 자릿수 반올림 방식에 따라 실제 표시가와 1~2원 어긋날 수
 * 있는 근사치 - 정확한 회계용이 아니라 "이만큼 아꼈어요" 체감용 숫자다.
 */
export function savingsAmount(product: { price: number; discountRate: number }): number {
  const originalPrice = product.price / (1 - product.discountRate / 100);
  return Math.round(originalPrice) - product.price;
}
