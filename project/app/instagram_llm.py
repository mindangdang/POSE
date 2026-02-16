import os
import json
import requests
from io import BytesIO
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv() # 이 함수가 실행되면서 .env 안의 내용을 os.environ에 싹 넣어줍니다.

# 1. API 키 설정 (이제 알아서 .env에서 가져옵니다)
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
genai.configure(api_key=api_key)

# 2. 메인 분석 함수
def extract_fact_and_vibe(image_url: str, caption: str, hashtags: list):
    print("⚡ [Gemini 1.5 Flash] 이미지와 텍스트를 통합 분석 중입니다...")

    # 이미지를 메모리로 다운로드하여 PIL 객체로 변환 (Codespaces 테스트용)
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))

    # 해시태그 통합
    tags_str = " ".join(hashtags)
    text_input = f"캡션: {caption}\n해시태그: {tags_str}"

    # 3. 핵심 프롬프트 (스키마 강제 및 OCR+Vibe 동시 추출)
    prompt = """
    너는 인스타그램 게시물을 분석하는 최고 수준의 데이터 추출 AI야.
    사용자가 제공한 '이미지'와 '캡션+해시태그'를 종합적으로 분석해줘.

    [작업 지시]
    1. 사진 속에 있는 글자(OCR)를 읽고, 조명, 인테리어, 색감 등 시각적인 분위기(Visual Vibe)를 파악해.
    2. 캡션과 해시태그의 맥락을 결합해.
    3. 아래의 JSON 스키마에 맞춰 '객관적 사실(fact_conditions)'과 '주관적 감성(vibe_text)'으로 완벽하게 분리해.

    [JSON 스키마 규격]
    {
      "fact_conditions": {
        "category": "맛집, 카페, 패션, 전시, 꿀팁 중 택 1",
        "location": "가게 이름이나 지역 명칭 (모르면 null)",
        "price_info": "가격대나 가성비 관련 정보 (모르면 null)",
        "key_items": ["주요 메뉴, 아이템, 사물 등 핵심 명사 2~3개"]
      },
      "vibe_text": "사진의 시각적 느낌, OCR로 읽은 의미 있는 글귀, 장소의 무드, 방문하기 좋은 상황(맥락) 등을 모두 자연스럽게 녹여낸 2~3문장의 줄글. (나중에 임베딩 벡터로 변환될 핵심 데이터임)"
    }
    """

    # 4. Gemini 1.5 Flash 호출 (JSON 출력 강제)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config={"response_mime_type": "application/json"}
    )
    
    # 프롬프트, 이미지 객체, 텍스트를 한 번에 리스트로 묶어서 전달
    response = model.generate_content([prompt, img, text_input])

    return json.loads(response.text)

# ==========================================
# 🚀 실행 테스트
# ==========================================
if __name__ == "__main__":
    # 가상의 인스타그램 데이터 세팅 (어둡고 분위기 있는 와인바 사진 예시)
    test_image_url = "https://images.unsplash.com/photo-1514362545857-3bc16c4c7d1b?q=80&w=1000&auto=format&fit=crop"
    test_caption = "오랜만에 찾은 보석 같은 곳🍷 간판이 없어서 한참 헤맸는데 들어오자마자 분위기에 압도당함. 신청곡도 틀어주시고 혼술하기 너무 좋을 듯. (와인 바틀 5만원대부터 시작!)"
    test_hashtags = ["#을지로바이브", "#나만알고싶은곳", "#와인바추천", "#퇴폐미", "#느좋"]

    # 분석 실행
    result_json = extract_fact_and_vibe(test_image_url, test_caption, test_hashtags)
    
    print("\n✅ 분석 완료! (PostgreSQL DB 적재용 데이터)")
    print(json.dumps(result_json, ensure_ascii=False, indent=2))