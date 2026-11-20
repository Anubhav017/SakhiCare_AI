from typing import Annotated, Literal
from pydantic import BaseModel, Field

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    source: Literal["pdf", "database", "hybrid", "guidelines"] = "hybrid"
    document_id: int | None = None
    language: Literal["en", "hi"] = "en"
    previous_questions: list[Annotated[str, Field(min_length=3, max_length=2000)]] = Field(
        default_factory=list, max_length=3
    )

class AskResponse(BaseModel):
    answer: str
    source: str
    references: list[dict]
