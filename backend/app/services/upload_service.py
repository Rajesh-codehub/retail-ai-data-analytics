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
from app.core.config import UPLOAD_DIR, MAX_FILE_SIZE, ALLOWED_EXTENSIONS, CHUNK_SIZE





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


def _validate_csv_file(file_path: Path) -> int:
    """Validate a CSV file and return the number of data rows.

    Raises HTTPException if the file is empty or unreadable.
    """
    try:
        with file_path.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read CSV file: {exc}",
        ) from exc

    if len(lines) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty — no data rows found (only header or nothing)",
        )

    return len(lines) - 1  # exclude header


def _validate_excel_file(file_path: Path) -> int:
    """Validate an Excel (.xlsx) file and return the number of data rows.

    Raises HTTPException if the file is empty, unreadable, or has no sheets with data.
    """
    try:
        import pandas as pd

        df = pd.read_excel(file_path, engine="openpyxl")
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Excel support not available — install openpyxl and pandas",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read Excel file: {exc}",
        ) from exc

    if df.empty or len(df) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Excel file is empty — no data rows found",
        )

    return len(df)


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
        # if normalized_dataset not in ALLOWED_DATASETS:
        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST,
        #         detail="Invalid dataset_type. Must be 'sales' or 'inventory'.",
        #     )

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

        # Validate file content based on type
        if ext == ".csv":
            row_count = _validate_csv_file(destination)
        elif ext == ".xlsx":
            row_count = _validate_excel_file(destination)
        else:
            row_count = 0

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


def get_upload_preview(
    db: Session,
    upload_id: UUID,
    current_user: User,
    rows: int = 10,
) -> dict:
    """Get a preview of an uploaded file (first N rows).

    Raises HTTPException if file not found, access denied, or unreadable.
    """
    # Reuse the same access control as get_upload_file_by_id
    record = get_upload_file_by_id(db, upload_id, current_user)

    file_path = Path(record.storage_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file not found on disk",
        )

    ext = record.file_type.lower()
    preview_rows = min(max(rows, 1), 100)  # clamp between 1 and 100

    try:
        if ext == "csv":
            import csv

            with file_path.open("r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="CSV file is empty — no header row",
                    )
                data_rows = []
                for i, row in enumerate(reader):
                    if i >= preview_rows:
                        break
                    data_rows.append(dict(zip(header, row)))

            # Count total rows for context
            total_rows = 0
            with file_path.open("r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                for _ in reader:
                    total_rows += 1

            return {
                "id": record.id,
                "original_filename": record.original_filename,
                "file_type": record.file_type,
                "columns": header,
                "total_rows": total_rows,
                "preview_rows": len(data_rows),
                "data": data_rows,
            }

        elif ext == "xlsx":
            import pandas as pd

            df = pd.read_excel(file_path, engine="openpyxl", nrows=preview_rows)
            columns = df.columns.tolist()
            data_rows = df.to_dict(orient="records")

            # Count total rows
            df_full = pd.read_excel(file_path, engine="openpyxl")
            total_rows = len(df_full)

            return {
                "id": record.id,
                "original_filename": record.original_filename,
                "file_type": record.file_type,
                "columns": columns,
                "total_rows": total_rows,
                "preview_rows": len(data_rows),
                "data": data_rows,
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Preview not supported for file type '{ext}'",
            )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview file: {exc}",
        ) from exc