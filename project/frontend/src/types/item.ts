export interface SavedItem {
  product_id: number;
  title: string;
  price: number | null;
  currency: string;
  brand: string | null;
  category: string;
  is_soldout: boolean | null;
  image_url: string;
  image_vector: string | null;
  shop: string;
  source_url: string;
  created_at: string;
}
