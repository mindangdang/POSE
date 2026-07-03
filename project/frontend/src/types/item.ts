export interface SavedItem {
  item_id: number;  
  title: string;
  price: number | null;
  brand: string | null;
  category: string;
  is_available: boolean | null;
  image_url: string;
  image_vector: string | null;
  shop: string;
  source_url: string;
  created_at: string;
}
