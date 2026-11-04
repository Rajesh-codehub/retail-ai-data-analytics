# app/models/product.py
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List
from sqlalchemy import DateTime, ForeignKey, Numeric, String, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)
    
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="pcs", nullable=False)
    default_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Use string references for relationships
    category: Mapped["Category"] = relationship(back_populates="products")
    sales_lines: Mapped[List["Sale"]] = relationship(back_populates="product")