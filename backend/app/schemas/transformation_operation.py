from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransformationOperationBase(BaseModel):
    name: str = Field(..., description="Human-readable name for the operation")
    operation_type: str = Field(..., description="One of: rename, cast, strip, lowercase, parse_date")
    config: Dict[str, Any] = Field(default_factory=dict, description="Operation-specific parameters")
    is_builtin: bool = Field(default=False, description="Whether this is a built-in operation")


class TransformationOperationCreate(TransformationOperationBase):
    pass


class TransformationOperationUpdate(BaseModel):
    name: Optional[str] = None
    operation_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_builtin: Optional[bool] = None


class TransformationOperationResponse(TransformationOperationBase):
    id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransformationOperationListResponse(BaseModel):
    items: List[TransformationOperationResponse]
    total: int


# Built-in operation definitions for validation
BUILTIN_OPERATIONS: dict[str, dict] = {
    "rename": {
        "required_config": ["old_name", "new_name"],
        "description": "Rename a column",
    },
    "cast": {
        "required_config": ["column", "to_type"],
        "description": "Cast a column to a different type (string, integer, float, date, bool)",
        "allowed_types": ["string", "integer", "float", "date", "bool"],
    },
    "strip": {
        "required_config": ["column"],
        "description": "Strip whitespace from a string column",
    },
    "lowercase": {
        "required_config": ["column"],
        "description": "Convert a string column to lowercase",
    },
    "parse_date": {
        "required_config": ["column", "format"],
        "description": "Parse a column as dates using the given format string",
    },
}