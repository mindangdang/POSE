import json
import logging
from openai import AsyncOpenAI
from app.config import get_settings
from app.schemas import *
from app.prompts import *

settings = get_settings()
logger = logging.getLogger("ollama_service")

# OpenAI 클라이언트지만 URL을 Ollama로 변경하여 사용
client = AsyncOpenAI(
    base_url=settings.OLLAMA_BASE_URL,
    api_key=settings.OLLAMA_API_KEY
)

class ConceptTutorService:
    @staticmethod
    async def _call_ollama(system_prompt: str, user_prompt: str, response_model: type):
        try:
            # response_format={"type": "json_object"}는 Ollama 최신 버전에서 지원
            completion = await client.chat.completions.create(
                model=settings.MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}, 
                temperature=0.2 # 환각 방지를 위해 낮게 설정
            )
            
            raw_content = completion.choices[0].message.content
            logger.info(f"Ollama Raw Response: {raw_content}")
            
            # Pydantic을 이용한 검증 및 파싱
            parsed_json = json.loads(raw_content)
            return response_model(**parsed_json)
            
        except json.JSONDecodeError:
            logger.error("Ollama failed to produce valid JSON.")
            raise RuntimeError("AI가 유효한 JSON을 생성하지 못했습니다. 다시 시도해주세요.")
        except Exception as e:
            logger.error(f"Ollama Error: {str(e)}")
            raise e

    @classmethod
    async def get_prerequisites(cls, concept: str) -> PrerequisiteResponse:
        return await cls._call_ollama(SYSTEM_PREREQUISITE, f"Concept: {concept}", PrerequisiteResponse)

    @classmethod
    async def diagnose(cls, req: LearningStateRequest) -> DiagnosisResponse:
        desc = "\n".join([f"- {i.concept}: {i.description}" for i in req.user_descriptions])
        return await cls._call_ollama(SYSTEM_DIAGNOSIS, f"Target: {req.target_concept}\nUser Notes:\n{desc}", DiagnosisResponse)

    @classmethod
    async def explain_mechanism(cls, req: MechanismExplainRequest) -> MechanismResponse:
        return await cls._call_ollama(SYSTEM_MECHANISM, f"Concept: {req.target_concept}, Weakness: {req.weak_concepts}", MechanismResponse)

    @classmethod
    async def generate_aha_moment(cls, req: AhaRequest) -> AhaResponse:
        return await cls._call_ollama(SYSTEM_AHA, f"Concept: {req.concept}, Confusion: {req.confusion_point}", AhaResponse)

    @classmethod
    async def recommend_materials(cls, req: MaterialRequest) -> MaterialResponse:
        return await cls._call_ollama(SYSTEM_MATERIAL, f"Concept: {req.concept}", MaterialResponse)