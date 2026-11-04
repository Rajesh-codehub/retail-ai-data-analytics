# app/models/branch.py
import uuid
from datetime import datetime
from typing import List
from sqlalchemy import DateTime, Integer, String, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    branch_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    branch_name: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Use string references inside relationships
    users: Mapped[List["User"]] = relationship(back_populates="branch", cascade="all, delete-orphan")
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="branch", cascade="all, delete-orphan")