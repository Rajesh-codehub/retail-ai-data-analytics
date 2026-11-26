# app/models/transformation_operation.py
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import DateTime, ForeignKey, String, UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class TransformationOperation(Base):
    __tablename__ = "transformation_operations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)  # rename, cast, strip, lowercase, parse_date
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # operation-specific parameters
    is_builtin: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", backref="transformation_operations")