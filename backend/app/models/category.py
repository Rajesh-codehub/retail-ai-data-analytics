# app/models/category.py
import uuid
from typing import List
from sqlalchemy import String, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    category_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Use string reference
    products: Mapped[List["Product"]] = relationship(back_populates="category", cascade="all, delete-orphan")