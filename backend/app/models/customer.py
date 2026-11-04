# app/models/customer.py
import uuid
from datetime import datetime
from typing import List
from sqlalchemy import DateTime, String, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    customer_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Use string reference here
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="customer")