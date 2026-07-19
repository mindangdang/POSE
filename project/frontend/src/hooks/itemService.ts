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
    await apiJson('/api/items/manual', {
      method: 'POST',
      body: JSON.stringify({
        item_id: item.item_id,
        user_id: user.id,
        source_url: item.source_url,
        category: item.category,
        image_url: item.image_url,
        image_vector: item.image_vector,
        price: item.price,
        brand: item.brand,
        is_available: item.is_available,
        shop: item.shop
      })
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
