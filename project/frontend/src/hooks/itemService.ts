import { apiJson } from '../lib/api';
import type { SavedItem } from '../types/item';
import type { AppUser } from '../types/user';

export async function saveItemToFeed(
  user: AppUser,
  item: SavedItem,
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>,
  refreshItems: () => Promise<void>
): Promise<void> {
  try {
    const payload = {
      ...(typeof item.product_id === 'number' && Number.isFinite(item.product_id)
        ? { product_id: item.product_id }
        : {}),
      title: item.title,
      source_url: item.source_url,
      category: item.category,
      image_url: item.image_url,
      image_vector: item.image_vector,
      price: item.price,
      currency: item.currency,
      brand: item.brand,
      is_soldout: item.is_soldout,
      shop: item.shop,
      likes: item.likes,
      dislikes: item.dislikes,
    };

    await apiJson('/api/items/manual', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    onItemsChange((prev: SavedItem[]) => [{ ...item, id: Date.now(), created_at: new Date().toISOString() }, ...prev]);
    void refreshItems();
    alert("피드에 저장되었습니다!");
  } catch (error: any) {
    console.error(error);
    alert(error.message);
    throw error; // Re-throw to allow calling component to handle if needed
  }
}
