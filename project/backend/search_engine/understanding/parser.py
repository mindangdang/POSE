from __future__ import annotations

import httpx

from project.backend.search_engine.schemas import Preference, SearchContext, SearchIntent
from project.backend.search_engine.understanding.intent_parser import DeterministicIntentParser
from project.backend.search_engine.understanding.llm import OpenAICompatibleIntentClient


class IntentParser:
    def __init__(self, use_llm: bool = True):
        self.fallback = DeterministicIntentParser()
        self.llm = OpenAICompatibleIntentClient() if use_llm else None
        self.last_retry_count = 0

    async def parse(
        self,
        query: str,
        context: SearchContext,
        preferences: list[Preference],
    ) -> tuple[SearchIntent, str | None]:
        if self.llm:
            try:
                parsed = await self.llm.parse_intent(query, context, preferences)
                self.last_retry_count = self.llm.last_retry_count
                return parsed, None
            except httpx.HTTPError as exc:
                self.last_retry_count = self.llm.last_retry_count
                return await self.fallback.parse(query, context, preferences), (
                    f"LLM intent parsing fell back: {type(exc).__name__}"
                )
            except Exception as exc:
                self.last_retry_count = self.llm.last_retry_count
                return await self.fallback.parse(query, context, preferences), (
                    f"LLM intent parsing fell back: {type(exc).__name__}"
                )
        return await self.fallback.parse(query, context, preferences), None
