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
  /** 같은 상품의 박스/개수만 다른 다른 리스팅들 - groupPackVariants가 붙인다. */
  variants?: Product[];
};

export type SortKey = 'recommend' | 'discount' | 'price';
