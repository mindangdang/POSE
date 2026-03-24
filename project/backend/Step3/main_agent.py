import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from project.backend.Step3.mcp_client import call_mcp_tool 

class VibeSearchAgent:
    def __init__(self, user_id: int):
        load_dotenv()
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.my_proxy_url = "https://lucky-bush-20ba.dear-m1njn.workers.dev" 
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                base_url=self.my_proxy_url
            )
        )
        self.user_id = user_id
        
        # ==========================================
        # 1. 도구 설명서(Tool Declaration) 정의
        # ==========================================
        # 제미나이에게 "이런 상황일 때 이 도구를 써라"라고 알려주는 명세서입니다.
        self.taste_tool = types.FunctionDeclaration(
            name="trigger_vibe_search",
            description="사용자가 장소, 물건, 콘텐츠(카페, 옷, 공간 등)를 '추천'해달라고 하거나, 개인의 미학적 취향과 바이브가 반영되어야 하는 질문을 했을 때 반드시 이 함수를 호출하세요. 일반적인 사실 검색(예: 날씨, 단순 지식)에는 호출하지 마세요.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "extracted_intent": types.Schema(
                        type=types.Type.STRING, 
                        description="사용자가 찾고자 하는 대상과 핵심 의도를 간략히 요약 (예: '서촌의 조용한 북카페')"
                    )
                },
                required=["extracted_intent"]
            )
        )
        self.tools = [types.Tool(function_declarations=[self.taste_tool])]

    def _get_embedding(self, text: str) -> list[float]:
        response = self.client.models.embed_content(
            model="gemini-embedding-2-preview", 
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=768 # DB 스키마(768차원)와 강제 동기화
            )
        )
        return response.embeddings[0].values

    def _execute_vibe_pipeline(self, user_query: str) -> str:
        """제미나이가 Vibe Search를 승인했을 때 실행되는 핵심 파이프라인"""
        
        # 1. 쿼리 벡터화
        print("   [Step 1] 사용자 질문을 수학적 주파수(Vector)로 변환합니다...")
        query_vector = self._get_embedding(user_query)
        
        # 2. 취향 맥락 수집 (MCP 1 호출)
        print("   [Step 2] 취향 MCP에 접근하여 맥락(Vibe Context)을 분석합니다...")
        vibe_context = call_mcp_tool(
            "get_taste_context", 
            user_query=user_query, 
            query_vector=query_vector, 
            user_id=self.user_id
        )
        print(f"      => 도출된 취향: {vibe_context}")
        
        # 3. 쿼리 확장 (MCP 2 호출)
        print("   [Step 3] 검색 엔진 노이즈를 걷어낼 Dorks(검색어)를 설계합니다...")
        expanded_queries_str = call_mcp_tool(
            "expand_search_queries", 
            user_query=user_query, 
            vibe_context=vibe_context
        )
        
        # 2. 텍스트를 파이썬 리스트 구조로 다시 변환합니다.
        try:
            expanded_queries = json.loads(expanded_queries_str)
        except json.JSONDecodeError:
            # (만약 LLM이 JSON 형식을 어겼을 경우를 대비한 안전 장치)
            expanded_queries = [expanded_queries_str] 

        #  3. 정상적인 리스트가 되었으므로, 이제 한 줄씩 예쁘게 출력됩니다.
        for q in expanded_queries:
            print(f"      =>  Dork: {q}")
            
        # 4. 구글 검색을 통한 최종 큐레이션 (Gemini Search Grounding)
        print("   [Step 4] 제미나이가 구글 웹 검색을 수행하고 최종 답변을 큐레이팅합니다...")
        prompt = f"""
        당신은 하이엔드 라이프스타일 큐레이터입니다.
        
        [사용자 원본 질문]: "{user_query}"
        [사용자 취향 맥락]: "{vibe_context}"
        [최적화된 검색 쿼리들]: {expanded_queries}
        
        [Instruction]
        1. 부여된 '구글 검색 기능'을 활용하여 위 [최적화된 검색 쿼리들]로 실제 웹 검색을 수행하세요.
        2. 양산형 블로그나 광고는 배제하고, 사용자의 '취향 맥락'과 시각적/감각적으로 완벽히 일치하는 결과 1~2개만 엄선하세요.
        3. 고급 매거진의 에디터처럼 통찰력 있고 매혹적인 톤앤매너로 답변을 작성하세요.
        """
        
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}], # 구글 검색 도구 활성화
                temperature=0.7
            )
        )
        return response.text

    def run(self, user_query: str) -> str:
        """메인 에이전트 라우팅 및 실행"""
        print(f"\n [User Query] '{user_query}'")
        print("에이전트가 질문의 성격을 판단 중입니다...")
        
        # 제미나이에게 도구 설명서를 쥐여주고 판단을 맡깁니다.
        response = self.client.models.generate_content(
            model='gemini-2.5-flash', # 라우팅 판단은 빠르고 저렴한 flash 모델 사용 권장
            contents=user_query,
            config=types.GenerateContentConfig(
                tools=self.tools,
                temperature=0.0 # 냉철한 판단을 위해 창의성 제거
            )
        )
        
        # 제미나이가 도구(trigger_vibe_search)를 사용하기로 결정했는지 확인합니다.
        if response.function_calls:
            for function_call in response.function_calls:
                if function_call.name == "trigger_vibe_search":
                    print("[판단 결과] 이 질문은 개인의 '취향 분석'이 필요합니다. Vibe Search를 가동합니다.\n")
                    return self._execute_vibe_pipeline(user_query)
        
        # 도구를 호출하지 않은 경우 (일반적인 대화나 단순 정보 검색)
        print(" [판단 결과] 단순 지식/대화형 질문입니다. 즉시 답변을 생성합니다.\n")
        
        # 구글 검색만 켜서 일반적인 답변 제공
        standard_response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_query,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}] 
            )
        )
        return standard_response.text

# ==========================================
# 실행부 테스트
# ==========================================
if __name__ == "__main__":
    TEST_USER_ID = 1
    agent = VibeSearchAgent(user_id=TEST_USER_ID)
    
    # 케이스 1: 취향 분석이 필요한 질문 (Vibe Search 파이프라인 가동됨)
    print("\n--- [Test Case 1] ---")
    answer1 = agent.run("이번 주말에 서촌에서 책 읽을 만한 조용한 카페 추천해 줘")
    print("\n [최종 결과]\n", answer1)
    
    # 케이스 2: 취향 분석이 필요 없는 일반 질문 (바로 답변함)
    print("\n--- [Test Case 2] ---")
    answer2 = agent.run("서촌은 어느 구에 위치해 있어?")
    print("\n [최종 결과]\n", answer2)