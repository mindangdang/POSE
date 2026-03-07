import os
from google import genai
from google.genai import types

# 가상의 MCP 클라이언트 호출 함수 (LangChain이나 직접 구현한 통신 모듈로 대체)
from mcp_client import call_mcp_tool 

class VibeSearchAgent:
    def __init__(self, user_id: int):
        self.user_id = user_id
        # Gemini 클라이언트 초기화
        self.genai_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        
    def _get_embedding(self, text: str) -> list[float]:
        """1단계: 사용자의 텍스트 질문을 벡터로 변환합니다."""
        print("1️⃣ 사용자 질문의 주파수(Vector)를 계산 중...")
        response = self.genai_client.models.embed_content(
            model='text-embedding-004',
            contents=text,
        )
        return response.embeddings[0].values

    def _search_and_synthesize(self, user_query: str, vibe_context: str, expanded_queries: list[str]) -> str:
        """4단계: 제미나이의 구글 검색 기능을 켜고, 큐레이션 답변을 생성합니다."""
        print("4️⃣ 제미나이가 구글 검색을 수행하고 큐레이팅을 시작합니다...")
        
        prompt = f"""
        당신은 하이엔드 라이프스타일 큐레이터이자 예리한 웹 리서처입니다.
        
        [사용자 원본 질문]: "{user_query}"
        [사용자 취향 맥락]: "{vibe_context}"
        [우리가 설계한 최적의 검색 쿼리들]: {expanded_queries}
        
        [Instruction]
        1. 당신에게 부여된 '구글 검색 기능'을 활용하여, 위 [최적의 검색 쿼리들]을 기반으로 실제 웹 검색을 수행하세요.
        2. 단순 네이버/블로그 양산형 글이 아닌, 감도 높은 매거진, 큐레이션 글, 독립 웹진 등의 결과를 위주로 탐색하세요.
        3. 검색 결과 중에서 사용자의 '취향 맥락'과 시각적/감각적으로 가장 잘 맞는 장소나 아이템 1~2개만 엄선하세요.
        4. 광고성 멘트나 흔한 블로그 말투는 철저히 배제하고, 고급 매거진의 에디터가 사용자만을 위해 작성한 듯한 통찰력 있는 문장으로 대답하세요.
        """
        
        # 핵심 포인트: tools 파라미터에 google_search를 추가하여 그라운딩(Grounding) 활성화
        response = self.genai_client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}], # 구글 검색 툴 온!
                temperature=0.7
            )
        )
        
        # (선택) 제미나이가 어떤 웹사이트를 참고했는지 출처(Grounding Metadata)도 확인할 수 있습니다.
        # if response.candidates[0].grounding_metadata:
        #     print("참고한 웹 문서 출처:", response.candidates[0].grounding_metadata.web_search_queries)
            
        return response.text

    def run(self, user_query: str) -> str:
        """메인 에이전트의 전체 워크플로우 실행"""
        print(f"\n🎯 [Vibe Search 시작] Query: '{user_query}'")
        
        # Step 1: 쿼리 임베딩
        query_vector = self._get_embedding(user_query)
        
        # Step 2: MCP 도구 호출 -> 취향 맥락 수집
        print("2️⃣ 취향 MCP 서버에 맥락 분석을 요청합니다...")
        vibe_context = call_mcp_tool(
            tool_name="get_taste_context", 
            user_query=user_query, 
            query_vector=query_vector, 
            user_id=self.user_id
        )
        print(f"   => [Context] {vibe_context}")
        
        # Step 3: MCP 도구 호출 -> 쿼리 확장 (Dorks 생성)
        print("3️⃣ 취향 맥락을 바탕으로 검색 설계(Query Expansion)를 진행합니다...")
        expanded_queries = call_mcp_tool(
            tool_name="expand_search_queries", 
            user_query=user_query, 
            vibe_context=vibe_context
        )
        for q in expanded_queries:
            print(f"   => [Dork] {q}")
            
        # Step 4: 구글 검색 + 큐레이션 (Gemini Native)
        final_answer = self._search_and_synthesize(user_query, vibe_context, expanded_queries)
        
        print("\n✨ [최종 큐레이션 결과]")
        return final_answer

# ==========================================
# 실행부
# ==========================================
if __name__ == "__main__":
    TEST_USER_ID = 1
    agent = VibeSearchAgent(user_id=TEST_USER_ID)
    
    answer = agent.run("이번 주말에 서촌에서 책 읽을 만한 곳 추천해 줘")
    print("====================================")
    print(answer)