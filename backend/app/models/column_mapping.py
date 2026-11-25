# app/models/column_mapping.py
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import DateTime, ForeignKey, String, UUID, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ColumnMapping(Base):
    __tablename__ = "column_mappings"

    __table_args__ = (
        UniqueConstraint(
            "dataset_type",
            "source_column",
            name="uq_column_mapping_dataset_source",
        ),
        UniqueConstraint(
            "dataset_type",
            "target_field",
            name="uq_column_mapping_dataset_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    dataset_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_column: Mapped[str] = mapped_column(String(100), nullable=False)
    target_field: Mapped[str] = mapped_column(String(100), nullable=False)
    is_template: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", backref="column_mappings")