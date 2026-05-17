import asyncio
import os
import json
import httpx
import psycopg
from tqdm.asyncio import tqdm
from project.backend.app.core.settings import load_backend_env

# Load environment variables
load_backend_env()
NEON_DB_URL = os.environ.get("NEON_DB_URL")
FRUITS_GRAPHQL_URL = "https://web-server.production.fruitsfamily.com/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Limit concurrency to be respectful to the API and DB
CONCURRENCY_LIMIT = 5
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

async def fetch_brand_details_async(client, brand_name):
    """Finds the Fruits Family brand ID and description for a given name."""
    payload = {
        "operationName": "getBrandByNameResponse",
        "variables": {"name": brand_name},
        "query": """
        query getBrandByNameResponse($name: String!) {
            getBrandByNameResponse(name: $name) {
                code
                brand { id description }
            }
        }
        """
    }
    res = await client.post(FRUITS_GRAPHQL_URL, json=payload, headers=HEADERS)
    res.raise_for_status()
    data = res.json()
    if "errors" in data:
        raise Exception(f"GraphQL Error: {data['errors']}")
    brand_resp = data.get("data", {}).get("getBrandByNameResponse", {})
    if brand_resp.get("code") == 200 and brand_resp.get("brand"):
        brand_obj = brand_resp["brand"]
        return brand_obj.get("id"), brand_obj.get("description")
    return None, None

async def get_similar_brands_async(client, brand_id):
    """Fetches similar brands based on a brand ID."""
    payload = {
        "operationName": "getSimilarBrands",
        "variables": {"brand_id": int(brand_id)},
        "query": """
        query getSimilarBrands($brand_id: Int!) {
            getSimilarBrands(brand_id: $brand_id) {
                id
                name
                name_kr
            }
        }
        """
    }
    res = await client.post(FRUITS_GRAPHQL_URL, json=payload, headers=HEADERS)
    res.raise_for_status()
    data = res.json()
    if "errors" in data:
        raise Exception(f"GraphQL Error: {data['errors']}")
    return data.get("data", {}).get("getSimilarBrands", [])

async def process_brand(client, conn, brand, existing_names):
    """Process a single brand: search ID -> find similar -> filter -> insert."""
    search_name = brand['brand_name_eng'] or brand['brand_name']
    
    try:
        async with semaphore:
            brand_id, description = await fetch_brand_details_async(client, search_name)
            if not brand_id:
                return None

            # 1. 현재 브랜드의 description이 비어있는 경우에만 업데이트
            if not brand.get('description') and description:
                print("insert a description")
                async with conn.cursor() as cur:
                    update_query = """
                    UPDATE brands 
                    SET description = %s 
                    WHERE (brand_name = %s OR brand_name_eng = %s) AND (description IS NULL OR description = '');
                    """
                    await cur.execute(update_query, (description, brand['brand_name'], brand['brand_name_eng']))
                

            # 2. 유사 브랜드 목록 가져오기
            similar_list = await get_similar_brands_async(client, brand_id)
            if not similar_list:
                return None

            # 3. 새로운 브랜드 필터링 및 상세 정보(description) 개별 조회
            candidates = []
            for s in similar_list:
                name_kr = s.get('name_kr') or s.get('name')
                if name_kr not in existing_names:
                    candidates.append(s)
                    existing_names.add(name_kr)

            if candidates:
                # 각 후보 브랜드의 상세 설명을 가져오기 위해 fetch_brand_details_async 호출
                desc_tasks = [fetch_brand_details_async(client, c.get('name')) for c in candidates]
                desc_results = await asyncio.gather(*desc_tasks)

                new_brands = []
                for c, (_, detail_desc) in zip(candidates, desc_results):
                    new_brands.append((
                        c.get('name_kr') or c.get('name'),
                        c.get('name'),
                        f"https://fruitsfamily.com/brand/{c.get('id')}",
                        json.dumps([]),
                        detail_desc
                    ))

                async with conn.cursor() as cur:
                    insert_query = """
                    INSERT INTO brands (brand_name, brand_name_eng, link, category_list, description)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (brand_name, link) DO NOTHING;
                    """
                    await cur.executemany(insert_query, new_brands)
                
                    await conn.commit()
                msg = f"✅ Processed '{search_name}'" + (f" & Added {len(new_brands)} new brands with descriptions" if new_brands else "")
                tqdm.write(msg)
        return None
    except Exception as e:
        return {"brand": search_name, "error": str(e)}

async def main():
    if not NEON_DB_URL:
        print("NEON_DB_URL not found in environment.")
        return

    async with await psycopg.AsyncConnection.connect(NEON_DB_URL, autocommit=False) as conn:
        async with conn.cursor() as cur:
            # 1. Ensure description column exists
            await cur.execute("ALTER TABLE brands ADD COLUMN IF NOT EXISTS description TEXT;")
            await conn.commit()

            await cur.execute("SELECT brand_name, brand_name_eng, description FROM brands")
            rows = await cur.fetchall()
            existing_brands = [{"brand_name": r[0], "brand_name_eng": r[1], "description": r[2]} for r in rows]
            existing_names_set = {r[0] for r in rows}

        tqdm.write(f"Found {len(existing_brands)} brands in database. Starting sync...")

        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [
                process_brand(client, conn, b, existing_names_set) 
                for b in existing_brands
            ]
            results = await tqdm.gather(*tasks, desc="Syncing brands", unit="brand")

    # 3. Summary Report
    errors = [r for r in results if r is not None]
    print("\n" + "="*50)
    print("📊 SYNC SUMMARY REPORT")
    print("-" * 50)
    print(f"Total brands processed: {len(existing_brands)}")
    print(f"Errors encountered:    {len(errors)}")
    
    if errors:
        print("\n❌ Error Details:")
        for err_info in errors:
            print(f"- {err_info['brand']}: {err_info['error']}")
    else:
        print("\n✨ All brands processed without critical errors.")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())