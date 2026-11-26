from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class AskRecordsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=300)
    worker: str | None = Field(default=None, min_length=1, max_length=180)
    previous_questions: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(
        default_factory=list, max_length=3
    )


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    source: Literal["pdf", "guidelines"] = "guidelines"
    document_id: int | None = None
    language: Literal["en", "hi"] = "en"
    previous_questions: list[Annotated[str, Field(min_length=3, max_length=2000)]] = Field(
        default_factory=list, max_length=3
    )

class AskResponse(BaseModel):
    answer: str
    source: str
    references: list[dict]
