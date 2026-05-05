import io
import asyncio
import httpx
import torch
from PIL import Image
import torch.nn.functional as F

# GPU 서버의 파이프라인 클래스 임포트
from embedding_reranking import FashionSiglipReRankingPipeline

async def load_image_from_url(url: str) -> Image.Image:
    """URL에서 이미지를 비동기로 다운로드하여 PIL Image 객체로 반환합니다."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=15.0, follow_redirects=True)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGB")


def get_image_no_cat_vector(self, img: Image.Image) -> list[float]:
        clean_img = self.preprocess_image(img)
        
        image_input = self.preprocess(clean_img).unsqueeze(0).to(self.device)
        if self.device == "cuda":
            image_input = image_input.to(torch.bfloat16)
        
        image_features = self.model.encode_image(image_input)
        img_vector = F.normalize(image_features, p=2, dim=1)
        image_vector = F.normalize(img_vector, p=2, dim=1)
        
        return image_vector[0].tolist()

async def main():
    images = [
        ["https://image.msscdn.net/thumbnails/images/goods_img/20240924/4458399/4458399_17273479266052_big.jpg?w=1200", "jeans"],
        ["https://image.msscdn.net/thumbnails/images/goods_img/20251119/5753503/5753503_17635382548509_big.jpg?w=1200", "ring"]
    ]

    pipeline = FashionSiglipReRankingPipeline()

    user_query = "denim pants" 
    query_vector = pipeline.encode_text(user_query)

    img_url = images[0][0]
    category = images[0][1]
        
    img_obj = await load_image_from_url(img_url)
    vec = torch.tensor([pipeline.get_image_vector(img_obj, category)]).to(pipeline.device)
    vec_no_cat = torch.tensor([get_image_no_cat_vector(pipeline, img_obj)]).to(pipeline.device)
    
    print(F.cosine_similarity(query_vector, vec).item())
    print(F.cosine_similarity(query_vector, vec_no_cat).item())

if __name__ == "__main__":
    asyncio.run(main())