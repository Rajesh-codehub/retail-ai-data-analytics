import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class ValidationIssue(Base):
    __tablename__ = "validation_issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    upload_file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("upload_files.id"),nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    column_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issue_code: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="error", nullable=False)  # error, warning, info
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    upload_file: Mapped["UploadFile"] = relationship(back_populates="validation_issues")