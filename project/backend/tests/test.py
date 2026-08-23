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

async def calculate_relative_probabilities(
    image_url: str, 
    candidate_texts: list[str], 
    logit_scale: float = 100.0
) -> dict[str, float]:
    """
    이미지와 여러 텍스트 후보군 간의 코사인 유사도를 구하고,
    CLIP 표준 Logit Scaling과 Softmax를 적용하여 상대적 확률(0~1)을 계산합니다.
    """
    # 1. 이미지 벡터와 각 텍스트 벡터를 비동기 병렬 추출 (지연 시간 최소화)
    image_task = _extract_vector_sync(image_url)
    text_tasks = [_extract_text_vector_sync(text) for text in candidate_texts]
    
    results = await asyncio.gather(image_task, *text_tasks)
    image_vector = np.array(results[0])
    text_vectors = [np.array(vec) for vec in results[1:]]

    # 2. 후보군 텍스트별 코사인 유사도 연산
    raw_similarities = np.array([
        cosine_similarity(image_vector, text_vec) 
        for text_vec in text_vectors
    ])

    # 3. Temperature Scaling 적용
    # CLIP은 통상 코사인 유사도에 exp(4.6052) ≈ 100 스케일을 곱해 Logit으로 사용합니다.
    logits = raw_similarities * logit_scale

    # 4. Softmax 정규화
    probabilities = softmax(logits)

    return {
        text: float(prob) 
        for text, prob in zip(candidate_texts, probabilities)
    }


if __name__ == "__main__":
    # 검증 대상: 앞서 첨부하신 밀리터리 자켓 이미지
    image_url = 'https://image.production.fruitsfamily.com/public/product/resized%40width1125/LW-ja5ihF-c2b95b2934d9.jpg'
    
    # 대조군 구성 (정답 타겟 + 형태/종류가 다른 오답 텍스트들)
    candidate_texts = [
        "a military jacket with shoulder epaulets", # 정답 타겟 (견장 자켓)
        "a basic formal black blazer",             # 대조군 1 (블레이저)
        "a denim jeans pants",                     # 대조군 2 (하의)
        "a plain white t-shirt"                    # 대조군 3 (이너웨어)
    ]
    
    results = asyncio.run(calculate_relative_probabilities(image_url, candidate_texts))
    
    print("\n=== 상대적 분류 확률 결과 ===")
    for text, prob in results.items():
        print(f"- {text:<45} : {prob * 100:.2f}%")

#python -m project.backend.tests.test