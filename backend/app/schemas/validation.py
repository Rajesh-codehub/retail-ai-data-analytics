from typing import Any, Optional
from pydantic import BaseModel, Field


class ColumnSchema(BaseModel):
    """Schema definition for a single column in an uploaded file."""
    required: bool = Field(default=False, description="Whether the column must be present")
    data_type: Optional[str] = Field(default=None, description="Expected type: 'string', 'integer', 'float', 'date', 'bool'")
    allowed_values: Optional[list[Any]] = Field(default=None, description="Allowed values if the column is categorical")
    min_value: Optional[float] = Field(default=None, description="Minimum value for numeric columns")
    max_value: Optional[float] = Field(default=None, description="Maximum value for numeric columns")


class DatasetSchema(BaseModel):
    """Schema definition for an entire dataset (e.g., sales or inventory)."""
    name: str = Field(..., description="Dataset name, e.g. 'sales' or 'inventory'")
    columns: dict[str, ColumnSchema] = Field(..., description="Column name -> schema mapping")
    allow_extra_columns: bool = Field(default=True, description="Whether columns not in the schema are allowed")