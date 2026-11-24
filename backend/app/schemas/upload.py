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


class UploadStatusResponse(BaseModel):
    id: UUID
    original_filename: str
    file_type: str
    status: str
    error_message: Optional[str] = None
    total_issues: int
    error_count: int
    warning_count: int
    uploaded_at: datetime


class ValidationIssueResponse(BaseModel):
    id: UUID
    row_number: int
    column_name: Optional[str] = None
    issue_code: str
    message: str
    severity: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ValidationIssueSummary(BaseModel):
    issue_code: str
    count: int


class ValidationIssuesResponse(BaseModel):
    items: List[ValidationIssueResponse]
    total: int
    summary: List[ValidationIssueSummary]