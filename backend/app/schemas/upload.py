from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UploadCreateResponse(BaseModel):
    id: UUID
    original_filename: str
    file_type: str
    file_size: int
    status: str
    message: str


class UploadDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uploaded_by: UUID
    original_filename: str
    file_type: str
    file_size: int
    status: str
    dataset_type: Optional[str] = None
    branch_id: Optional[UUID] = None
    file_hash: Optional[str] = None
    error_message: Optional[str] = None
    uploaded_at: datetime


class UploadListResponse(BaseModel):
    items: List[UploadDetailResponse]
    total: int


class UploadPreviewResponse(BaseModel):
    id: UUID
    original_filename: str
    file_type: str
    columns: List[str]
    total_rows: Optional[int] = None
    preview_rows: int
    data: List[dict[str, Any]]