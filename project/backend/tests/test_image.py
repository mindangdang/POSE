from project.backend.basic_functions.utils import _extract_text_vector_sync, _extract_vector_sync
import numpy as np
import asyncio

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    if vec1 is None or vec2 is None:
        return 0.0
    vec1 = np.array(vec1).flatten()
    vec2 = np.array(vec2).flatten()
    
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
        
    return float(np.dot(vec1, vec2) / (norm1 * norm2))

def softmax(logits: np.ndarray) -> np.ndarray:
    # 수치적 안정성을 위해 최대값을 감산 (Overflow 방지)
    shifted_logits = logits - np.max(logits)
    exp_logits = np.exp(shifted_logits)
    return exp_logits / np.sum(exp_logits)


async def search_images_by_text(
    query_text: str, 
    candidate_image_urls: list[str], 
    logit_scale: float = 100.0
) -> dict[str, float]:
    """
    단일 텍스트 쿼리에 대해 여러 후보 이미지 중 
    어떤 이미지가 가장 적합한지 상대적 확률을 계산합니다.
    """
    
    # 1. 텍스트 벡터 추출 (Query)
    text_vector = np.array(await _extract_text_vector_sync(query_text))
    
    # 2. 다중 이미지 벡터 병렬 추출 (Candidates)
    image_tasks = [_extract_vector_sync(url) for url in candidate_image_urls]
    image_results = await asyncio.gather(*image_tasks)
    image_vectors = [np.array(vec) for vec in image_results]

    # 3. 단일 텍스트 vs 다중 이미지 코사인 유사도 연산
    raw_similarities = np.array([
        cosine_similarity(text_vector, img_vec) 
        for img_vec in image_vectors
    ])

    # 4. Logit 변환 및 Softmax
    logits = raw_similarities * logit_scale
    probabilities = softmax(logits)

    # 5. 결과 매핑
    return {
        url: (float(sim), float(prob)) 
        for url, sim, prob in zip(candidate_image_urls, raw_similarities, probabilities)
    }

if __name__ == "__main__":
    # 테스트용 이미지 URL 리스트
    urls = [
        "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS_ZPRGyuTV921KgRH3pCqr5aNAdq6sR61uevXDbsC90w&s=10", # 나이키 샥스
        "https://item.elandrs.com/upload/prd/orgimg/458/1911835458_0000005.jpg?w=750&q=100",
        "https://static.nike.com/a/images/t_web_pw_592_v2/f_auto/u_9ddf04c7-2a9a-4d76-add1-d15af8f0263d,c_scale,fl_relative,w_1.0,h_1.0,fl_layer_apply/0708260a-b8ae-4cde-b40d-ce9d420eb58a/NIKE+P-6000.png"
    ]
    
    query = "street mood sneakers with a unique sole"
    probabilities = asyncio.run(search_images_by_text(query, urls))
    
    # 결과 출력
    for url, (sim, prob) in probabilities.items():
        print(f"Image URL: {url}, Similarity: {sim:.4f}, Probability: {prob:.4f}")

# python -m project.backend.tests.test_image