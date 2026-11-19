import hashlib
import uuid
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, UploadFile as FastAPIUploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.upload_file import UploadFile
from app.models.user import User

UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE = 1024 * 64  # 64 KB
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
ALLOWED_DATASETS = {"sales", "inventory"}


def _resolve_branch_id(current_user: User, requested_branch_id: Optional[UUID]) -> Optional[UUID]:
    role = (current_user.role or "").lower()

    if role == "admin":
        return requested_branch_id if requested_branch_id is not None else current_user.branch_id

    if (
        requested_branch_id is not None
        and current_user.branch_id is not None
        and requested_branch_id != current_user.branch_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not permitted to upload data for another branch",
        )
    return current_user.branch_id


def save_upload_file(
    db: Session,
    file: FastAPIUploadFile,
    current_user: User,
    dataset_type: Optional[str] = None,
    branch_id: Optional[UUID] = None,
) -> UploadFile:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext or 'none'}'. Only CSV and XLSX are allowed.",
        )

    normalized_dataset: Optional[str] = None
    if dataset_type is not None:
        normalized_dataset = dataset_type.strip().lower()
        if normalized_dataset not in ALLOWED_DATASETS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid dataset_type. Must be 'sales' or 'inventory'.",
            )

    resolved_branch_id = _resolve_branch_id(current_user, branch_id)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4()}{ext}"
    destination = UPLOAD_DIR / stored_filename

    total_bytes = 0
    hasher = hashlib.sha256()

    try:
        with destination.open("wb") as buffer:
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File size exceeds the 10 MB limit",
                    )
                hasher.update(chunk)
                buffer.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )

        record = UploadFile(
            uploaded_by=current_user.id,
            original_filename=file.filename,
            storage_path=str(destination),
            file_type=ext.lstrip("."),  # "csv" or "xlsx"
            file_size=total_bytes,
            status="uploaded",
            dataset_type=normalized_dataset,
            branch_id=resolved_branch_id,
            file_hash=hasher.hexdigest(),
        )

        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    except HTTPException:
        destination.unlink(missing_ok=True)
        db.rollback()
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store uploaded file",
        ) from exc
    finally:
        file.file.close()


def list_upload_files(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    dataset_type: Optional[str] = None,
) -> tuple[list[UploadFile], int]:
    role = (current_user.role or "").lower()
    query = db.query(UploadFile)

    if role == "admin":
        pass  # Admin sees all uploads
    elif role == "manager":
        if current_user.branch_id is not None:
            query = query.filter(UploadFile.branch_id == current_user.branch_id)
        else:
            query = query.filter(UploadFile.uploaded_by == current_user.id)
    else:
        # Employee sees their own uploads
        query = query.filter(UploadFile.uploaded_by == current_user.id)

    if status_filter:
        query = query.filter(UploadFile.status == status_filter.lower())
    if dataset_type:
        query = query.filter(UploadFile.dataset_type == dataset_type.lower())

    total = query.with_entities(func.count(UploadFile.id)).scalar() or 0
    items = (
        query.order_by(UploadFile.uploaded_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def get_upload_file_by_id(
    db: Session,
    upload_id: UUID,
    current_user: User,
) -> UploadFile:
    record = db.query(UploadFile).filter(UploadFile.id == upload_id).first()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )

    role = (current_user.role or "").lower()
    if role == "admin":
        return record
    if role == "manager":
        if current_user.branch_id is not None and record.branch_id == current_user.branch_id:
            return record
        if record.uploaded_by == current_user.id:
            return record
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if record.uploaded_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return record