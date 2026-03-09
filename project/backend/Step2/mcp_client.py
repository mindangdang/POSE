import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def call_mcp_tool_async(tool_name: str, arguments: dict) -> str:
    """MCP 서버와 연결하여 특정 도구를 실행하고 결과를 받아옵니다."""
    
    # 앞서 만든 FastMCP 서버 스크립트를 백그라운드 프로세스로 실행
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"] 
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # MCP 서버 초기화
            await session.initialize()
            
            # 서버에 등록된 도구 호출
            result = await session.call_tool(tool_name, arguments)
            
            # 결과 텍스트 추출 (결과는 보통 리스트 형태의 컨텐츠로 옴)
            return result.content[0].text

# 일반 동기(Sync) 코드에서 호출하기 위한 래퍼 함수
def call_mcp_tool(tool_name: str, **kwargs) -> str:
    return asyncio.run(call_mcp_tool_async(tool_name, kwargs))