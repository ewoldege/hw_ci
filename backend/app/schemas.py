from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class JobRunCreate(BaseModel):
    status: str = Field(default="queued", max_length=32)


class JobRunOut(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArtifactOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    name: str
    s3_key: str
    content_type: Optional[str]
    size: int
    created_at: datetime

    class Config:
        from_attributes = True


class ArtifactListOut(BaseModel):
    items: list[ArtifactOut]
