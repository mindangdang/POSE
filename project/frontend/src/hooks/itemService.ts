import type { SavedItem } from '../types/item';
import type { AppUser } from '../types/user';

export async function saveItemToFeed(
  user: AppUser,
  item: SavedItem,
  onItemsChange: React.Dispatch<React.SetStateAction<SavedItem[]>>,
  refreshItems: () => Promise<void>,
  refreshTaste: () => Promise<void>
): Promise<void> {
  try {
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch('/api/items/manual', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        user_id: user.id,
        category: item.category || "WEB SEARCH",
        sub_category: item.sub_category || "WEB SEARCH",
        recommend: item.recommend,
        facts: item.facts,
        url: item.url,
        image_url: item.image_url
      })
    });

    if (!res.ok) throw new Error("Failed to save result");

    onItemsChange((prev: SavedItem[]) => [{ ...item, id: Date.now(), created_at: new Date().toISOString() }, ...prev]);
    void refreshItems();
    alert("피드에 저장되었습니다!");
    await refreshTaste();
  } catch (error: any) {
    console.error(error);
    alert(error.message);
    throw error; // Re-throw to allow calling component to handle if needed
  }
}