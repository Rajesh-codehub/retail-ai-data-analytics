import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # e.g., receipt, sale, return, adjustment
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )  # Positive value; movement_type determines direction
    reference_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )  # e.g., transaction id or purchase order reference
    movement_time: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    branch: Mapped["Branch"] = relationship(backref="inventory_movements")
    product: Mapped["Product"] = relationship(backref="inventory_movements")