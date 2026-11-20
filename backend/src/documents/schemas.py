from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

DocumentStatus = Literal["pending", "processing", "ready", "failed"]


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: DocumentStatus
    guideline_language: Literal["hi", "en"] | None = None
    guideline_topic_key: str | None = None


class DocumentDetail(DocumentSummary):
    chunks: int
    indexing_error: str | None


class DocumentUploadResponse(BaseModel):
    document_id: int
    status: DocumentStatus
    chunks: int
    duplicate: bool


class GuidelineApproval(BaseModel):
    language: Literal["hi", "en"] | None = None
    topic_key: Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$", max_length=80)] | None = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
