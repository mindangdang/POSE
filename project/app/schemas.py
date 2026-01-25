from pydantic import BaseModel, Field
from typing import List, Dict, Literal

class KnowledgeItem(BaseModel):
    concept: str
    description: str

class PrerequisiteResponse(BaseModel):
    target_concept: str
    prerequisites: List[str]

class LearningStateRequest(BaseModel):
    target_concept: str
    user_descriptions: List[KnowledgeItem]

class DiagnosisResponse(BaseModel):
    understood_concepts: List[str]
    weak_concepts: List[str]
    misconceptions: List[str]
    learning_path_adjustment: Dict[str, str]

class MechanismExplainRequest(BaseModel):
    target_concept: str
    weak_concepts: List[str]

class MechanismResponse(BaseModel):
    core_mechanism: str
    analogy: str
    why_it_matters: str

class AhaRequest(BaseModel):
    concept: str
    confusion_point: str

class AhaResponse(BaseModel):
    paradigm_shift: str
    connection_insight: str

class MaterialRequest(BaseModel):
    concept: str

class MaterialItem(BaseModel):
    type: str
    title: str
    relevance: str

class MaterialResponse(BaseModel):
    resources: List[MaterialItem]