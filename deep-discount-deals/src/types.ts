export type Product = {
  name: string;
  price: number;
  discountRate: number;
  imageUrl: string;
  category: string;
  shareLink: string;
  reviewCount: number;
  dealEndsAt?: string;
  isAllTimeLow?: boolean;
  tacaItemId?: number;
  /** 같은 상품의 색상/용량/수량만 다른 리스팅들 - groupProductVariants가 붙인다. */
  variants?: Product[];
};

export type SortKey = 'recommend' | 'discount' | 'price';
