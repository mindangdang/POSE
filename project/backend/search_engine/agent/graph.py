from __future__ import annotations

from typing import Any, cast

from project.backend.search_engine.agent.state import SearchState


def build_search_graph(pipeline: Any, checkpoint_callback=None) -> Any:
    async def checkpoint(state: SearchState, update: dict) -> dict:
        merged = {**state, **update}
        if checkpoint_callback is not None:
            result = checkpoint_callback(merged)
            if hasattr(result, "__await__"):
                await result
        return update

    async def prepare(state: SearchState) -> dict:
        return await checkpoint(state, await pipeline.prepare(state))

    async def retrieve(state: SearchState) -> dict:
        return await checkpoint(state, await pipeline.retrieve(state))

    async def rank(state: SearchState) -> dict:
        return await checkpoint(state, await pipeline.rank(state))

    async def evaluate_coverage(state: SearchState) -> dict:
        return await checkpoint(state, await pipeline.evaluate_coverage(state))

    async def finalize(state: SearchState) -> dict:
        return await checkpoint(state, await pipeline.finalize(state))

    try:
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(SearchState)
        graph.add_node("prepare", prepare)
        graph.add_node("retrieve", retrieve)
        graph.add_node("rank", rank)
        graph.add_node("evaluate_coverage", evaluate_coverage)
        graph.add_node("finalize", finalize)
        graph.add_edge(START, "prepare")
        graph.add_conditional_edges(
            "prepare",
            lambda state: "finalize" if state.get("status") == "clarification_required" else "retrieve",
            {"retrieve": "retrieve", "finalize": "finalize"},
        )
        graph.add_edge("retrieve", "rank")
        graph.add_edge("rank", "evaluate_coverage")
        graph.add_conditional_edges(
            "evaluate_coverage",
            lambda state: "retrieve" if state.get("retry_reason") else "finalize",
            {"retrieve": "retrieve", "finalize": "finalize"},
        )
        graph.add_edge("finalize", END)
        return graph.compile()
    except ImportError:
        class SequentialFallback:
            async def ainvoke(self, state: dict) -> dict:
                current = await prepare(cast(SearchState, state))
                if current.get("status") != "clarification_required":
                    while True:
                        current = await retrieve(cast(SearchState, current))
                        current = await rank(cast(SearchState, current))
                        current = await evaluate_coverage(cast(SearchState, current))
                        if not current.get("retry_reason"):
                            break
                return await finalize(cast(SearchState, current))

        return SequentialFallback()
