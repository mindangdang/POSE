import os
import sys
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def call_mcp_tool_async(tool_name: str, arguments: dict) -> str:
    """MCP 서버와 연결하여 특정 도구를 실행하고 결과를 받아옵니다."""
    
    #  1. 현재 파일(mcp_client.py)의 절대 경로를 구해서 서버 파일의 위치를 정확히 고정합니다.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(current_dir, "mcp_server.py")
    
    #  2. 그냥 "python"을 호출하지 않고, 현재 실행 중인 파이썬 환경의 경로를 그대로 가져옵니다.
    python_executable = sys.executable
    
    server_params = StdioServerParameters(
        command=python_executable,
        args=[server_path] # 상대 경로("mcp_server.py") 대신 완벽한 절대 경로 주입
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # MCP 서버 초기화
            await session.initialize()
            
            # 서버에 등록된 도구 호출
            result = await session.call_tool(tool_name, arguments)
            
            # 결과 텍스트 추출
            return result.content[0].text

# 일반 동기(Sync) 코드에서 호출하기 위한 래퍼 함수
def call_mcp_tool(tool_name: str, **kwargs) -> str:
    return asyncio.run(call_mcp_tool_async(tool_name, kwargs))