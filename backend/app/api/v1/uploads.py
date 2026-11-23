from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.upload import (
    UploadCreateResponse,
    UploadDetailResponse,
    UploadListResponse,
    UploadPreviewResponse,
)
from app.services import upload_service
from app.services import validation_service
from app.services import data_quality_service

router = APIRouter(prefix="/api/v1/uploads", tags=["Uploads"])


@router.post(
    "/",
    response_model=UploadCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_file(
    file: UploadFile = File(...),
    dataset_type: Optional[str] = Form(default=None),
    branch_id: Optional[UUID] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = upload_service.save_upload_file(
        db=db,
        file=file,
        current_user=current_user,
        dataset_type=dataset_type,
        branch_id=branch_id,
    )
    return UploadCreateResponse(
        id=record.id,
        original_filename=record.original_filename,
        file_type=record.file_type,
        file_size=record.file_size,
        status=record.status,
        message="File uploaded successfully",
    )


@router.get(
    "/",
    response_model=UploadListResponse,
    status_code=status.HTTP_200_OK,
)
def list_uploads(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    dataset_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = upload_service.list_upload_files(
        db=db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        status_filter=status_filter,
        dataset_type=dataset_type,
    )
    return UploadListResponse(items=items, total=total)


@router.get(
    "/{upload_id}",
    response_model=UploadDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_upload_details(
    upload_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return upload_service.get_upload_file_by_id(
        db=db,
        upload_id=upload_id,
        current_user=current_user,
    )


@router.get(
    "/{upload_id}/preview",
    response_model=UploadPreviewResponse,
    status_code=status.HTTP_200_OK,
)
def preview_upload(
    upload_id: UUID,
    rows: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return upload_service.get_upload_preview(
        db=db,
        upload_id=upload_id,
        current_user=current_user,
        rows=rows,
    )


@router.post(
    "/{upload_id}/validate",
    status_code=status.HTTP_200_OK,
)
def validate_upload(
    upload_id: UUID,
    dataset_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return validation_service.validate_upload_file(
        db=db,
        upload_id=upload_id,
        dataset_type=dataset_type,
    )


@router.get(
    "/{upload_id}/profile",
    status_code=status.HTTP_200_OK,
)
def profile_upload(
    upload_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return data_quality_service.profile_upload_file(
        db=db,
        upload_id=upload_id,
    )