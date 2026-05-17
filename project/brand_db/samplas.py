import requests
from bs4 import BeautifulSoup

BASE_URL = "https://samplas.co.kr"
url = BASE_URL + "/brand.html"

headers = {
    "User-Agent": "Mozilla/5.0"
}

res = requests.get(url, headers=headers)
res.raise_for_status()

soup = BeautifulSoup(res.text, "html.parser")

brands = []

items = soup.select("div.brand_con")

for item in items:
    # 👉 링크
    a_tag = item.select_one(".brand_image a")
    if not a_tag:
        continue

    link = a_tag.get("href")
    full_link = BASE_URL + link if link.startswith("/") else link

    # 👉 브랜드명 (첫 줄만)
    name_tag = item.select_one(".brand_dec p")
    if not name_tag:
        continue

    raw_text = name_tag.get_text("\n", strip=True)
    name = raw_text.split("\n")[0].strip()

    try:
        cate_no = link.strip("/").split("/")[-1]
    except:
        cate_no = None

    brands.append({
        "brand_name": name,
        "link": full_link,
        "cate_no": cate_no
    })

print(f"총 브랜드 수: {len(brands)}")

for b in brands[:10]:
    print(b)