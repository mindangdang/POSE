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

    # ... (init과 _get_embedding 부분은 기존과 동일) ...

    def _execute_vibe_pipeline_stream(self, user_query: str):
        """제미나이가 Vibe Search를 승인했을 때 실행되는 핵심 파이프라인 (스트리밍 버전)"""
        
        # [UX 트릭] 프론트엔드에 지금 무슨 작업을 하고 있는지 먼저 한 줄씩 타자를 쳐줍니다.
        yield "질문의 숨은 의도를 파악하여 취향 DB를 탐색하고 있습니다...\n\n"
        
        # 1. 쿼리 벡터화
        query_vector = self._get_embedding(user_query)
        
        # 2. 취향 맥락 수집 (MCP 1 호출)
        vibe_context = call_mcp_tool(
            "get_taste_context", 
            user_query=user_query, 
            query_vector=query_vector, 
            user_id=self.user_id
        )
        
        yield "유저님의 미학적 취향 패턴을 분석 완료했습니다. 맞춤형 큐레이션을 시작합니다...\n\n"
        
        # 3. 쿼리 확장 (MCP 2 호출)
        expanded_queries_str = call_mcp_tool(
            "expand_search_queries", 
            user_query=user_query, 
            vibe_context=vibe_context
        )
        
        try:
            expanded_queries = json.loads(expanded_queries_str)
        except json.JSONDecodeError:
            expanded_queries = [expanded_queries_str] 

        yield "일반적인 노이즈를 걷어내고, 감도 높은 웹 검색을 수행 중입니다...\n\n---\n\n"
        
        # 4. 구글 검색을 통한 최종 큐레이션 (Streaming)
        prompt = f"""
        당신은 하이엔드 라이프스타일 큐레이터이다.
        
        [사용자 원본 질문]: "{user_query}"
        [사용자 취향 맥락]: "{vibe_context}"
        [최적화된 검색 쿼리들]: {expanded_queries}
        
        [Instruction]
        1. 부여된 '구글 검색 기능'을 활용하여 위 [최적화된 검색 쿼리들]을 활용해 실제 웹 검색을 수행하라.
        2. 양산형 블로그나 광고, 쿠팡 등의 싸구려 검색결과는 배제하고, 사용자의 '취향 맥락'과 페르소나를 만조시킬 수 있는 감도높은 결과만 엄선하라.
        """
        
        # generate_content_stream으로 변경하여 청크 단위로 받아옵니다.
        response_stream = self.client.models.generate_content_stream(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}], 
                temperature=0.5
            )
        )
        
        # 스트리밍 청크를 실시간으로 프론트엔드로 밀어냅니다(yield)
        for chunk in response_stream:
            if chunk.text:
                yield chunk.text

    def run_stream(self, user_query: str):
        """메인 에이전트 라우팅 및 실행 (스트리밍 반환)"""
        
        # 제미나이에게 판단을 맡깁니다. (이 작업은 1~2초 내에 끝나므로 스트리밍 생략)
        response = self.client.models.generate_content(
            model='gemini-2.5-flash-lite', 
            contents=user_query,
            config=types.GenerateContentConfig(
                tools=self.tools,
                temperature=0.0 
            )
        )
        
        # 도구(trigger_vibe_search)를 사용하기로 결정한 경우
        if response.function_calls:
            for function_call in response.function_calls:
                if function_call.name == "trigger_vibe_search":
                    # 파이프라인 제너레이터를 그대로 연결합니다.
                    yield from self._execute_vibe_pipeline_stream(user_query)
                    return
        
        # 도구를 호출하지 않은 경우 (일반 지식 검색)
        yield "일반 웹 검색을 통해 빠르고 정확한 답변을 생성 중입니다...\n\n"
        
        standard_response_stream = self.client.models.generate_content_stream(
            model='gemini-2.5-flash',
            contents=user_query,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}] 
            )
        )
        
        for chunk in standard_response_stream:
            if chunk.text:
                yield chunk.text

