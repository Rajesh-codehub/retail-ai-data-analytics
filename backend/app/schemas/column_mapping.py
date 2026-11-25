from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ColumnMappingBase(BaseModel):
    dataset_type: str = Field(..., description="Dataset type, e.g. 'sales' or 'inventory'")
    source_column: str = Field(..., description="Source column name from uploaded file")
    target_field: str = Field(..., description="Target field name (e.g. SKU, branch, quantity, price, date)")
    is_template: bool = Field(default=False, description="Whether this is a reusable template")


class ColumnMappingCreate(ColumnMappingBase):
    pass


class ColumnMappingUpdate(BaseModel):
    source_column: Optional[str] = Field(default=None)
    target_field: Optional[str] = Field(default=None)
    is_template: Optional[bool] = Field(default=None)


class ColumnMappingResponse(ColumnMappingBase):
    id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ColumnMappingListResponse(BaseModel):
    items: List[ColumnMappingResponse]
    total: int