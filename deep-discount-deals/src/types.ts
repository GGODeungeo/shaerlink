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
};
