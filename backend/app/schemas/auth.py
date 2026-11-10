import uuid
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):
    employee_id: str = Field(..., min_length=1, description="Unique employee identifier")
    name: str = Field(..., min_length=1, description="Full name of the user")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, description="Password with minimum 8 characters")
    role: Literal["admin", "manager", "employee"] = Field(default="employee", description="User role")
    branch_id: Optional[uuid.UUID] = Field(default=None, description="Optional branch UUID")

class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="User password")

class UserResponse(BaseModel):
    id: uuid.UUID
    employee_id: str
    name: str
    email: EmailStr
    role: str
    branch_id: Optional[uuid.UUID] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    email: Optional[EmailStr] = None
    role: Optional[Literal["admin", "manager", "employee"]] = None
    branch_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")