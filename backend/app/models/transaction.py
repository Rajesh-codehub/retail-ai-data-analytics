# app/models/transaction.py
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import DateTime, ForeignKey, Numeric, String, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    source_transaction_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), index=True, nullable=False)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    
    transaction_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Use string references for all relationships
    branch: Mapped["Branch"] = relationship(back_populates="transactions")
    customer: Mapped[Optional["Customer"]] = relationship(back_populates="transactions")
    sales: Mapped[List["Sale"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")