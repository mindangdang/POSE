from fastapi import FastAPI, Request
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from typing import List, Dict
from app.service import ConceptTutorService
from app.schemas import *

mcp_server = Server("ollama-tutor-mcp")

@mcp_server.tool()
async def get_prerequisites(concept: str) -> str:
    res = await ConceptTutorService.get_prerequisites(concept)
    return res.model_dump_json()

@mcp_server.tool()
async def diagnose_learning(target_concept: str, descriptions: List[Dict[str, str]]) -> str:
    items = [KnowledgeItem(**d) for d in descriptions]
    req = LearningStateRequest(target_concept=target_concept, user_descriptions=items)
    res = await ConceptTutorService.diagnose(req)
    return res.model_dump_json()

@mcp_server.tool()
async def explain_mechanism(target_concept: str, weak_concepts: List[str]) -> str:
    req = MechanismExplainRequest(target_concept=target_concept, weak_concepts=weak_concepts)
    res = await ConceptTutorService.explain_mechanism(req)
    return res.model_dump_json()

@mcp_server.tool()
async def aha_moment(concept: str, confusion_point: str) -> str:
    req = AhaRequest(concept=concept, confusion_point=confusion_point)
    res = await ConceptTutorService.generate_aha_moment(req)
    return res.model_dump_json()

@mcp_server.tool()
async def recommend_materials(concept: str) -> str:
    req = MaterialRequest(concept=concept)
    res = await ConceptTutorService.recommend_materials(req)
    return res.model_dump_json()

sse_transport = SseServerTransport("/messages")
app = FastAPI()

@app.get("/sse")
async def handle_sse(request: Request):
    async with mcp_server.run(sse_transport.incoming_messages, sse_transport.outgoing_messages):
        return await sse_transport.handle_sse(request)

@app.post("/messages")
async def handle_messages(request: Request):
    await sse_transport.handle_post_message(request)
    return {"status": "ok"}