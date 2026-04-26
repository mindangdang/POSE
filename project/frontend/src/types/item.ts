export interface SavedItem {
  id: number;
  url: string;
  category: string;
  sub_category: string;
  facts: Record<string, unknown> | string | null;
  recommend: string;
  image_url: string;
  created_at: string;
  summary_text?: string;
}
