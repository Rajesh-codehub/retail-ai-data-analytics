import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.load_run import LoadRun
    from app.models.transformation_job import TransformationJob
    from app.models.user import User
    from app.models.validation_issue import ValidationIssue


class UploadFile(Base):
    __tablename__ = "upload_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "csv" or "xlsx"
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # in bytes
    status: Mapped[str] = mapped_column(
        String(50), default="uploaded", nullable=False
    )  # uploaded, validating, validated, failed, loaded

    dataset_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "sales" or "inventory"
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True, index=True
    )
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="uploaded_files")
    validation_issues: Mapped[List["ValidationIssue"]] = relationship(
        back_populates="upload_file", cascade="all, delete-orphan"
    )
    transformation_jobs: Mapped[List["TransformationJob"]] = relationship(
        back_populates="upload_file", cascade="all, delete-orphan"
    )
    load_runs: Mapped[List["LoadRun"]] = relationship(
        back_populates="upload_file", cascade="all, delete-orphan"
    )