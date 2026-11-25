from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.column_mapping import (
    ColumnMappingCreate,
    ColumnMappingListResponse,
    ColumnMappingResponse,
    ColumnMappingUpdate,
)
from app.services import column_mapping_service

router = APIRouter(prefix="/api/v1/mappings", tags=["Column Mappings"])


@router.post(
    "/",
    response_model=ColumnMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mapping(
    mapping_data: ColumnMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new column mapping for a dataset type.

    Required targets for sales: sku, branch, quantity, price, date
    Required targets for inventory: sku, branch, quantity_on_hand, reorder_level, date
    """
    return column_mapping_service.create_column_mapping(
        db=db,
        mapping_in=mapping_data,
        created_by=current_user.id,
    )


@router.get(
    "/",
    response_model=ColumnMappingListResponse,
    status_code=status.HTTP_200_OK,
)
def list_mappings(
    dataset_type: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List column mappings, optionally filtered by dataset type."""
    items, total = column_mapping_service.get_column_mappings(
        db=db,
        dataset_type=dataset_type,
        skip=skip,
        limit=limit,
    )
    return ColumnMappingListResponse(items=items, total=total)


@router.get(
    "/{mapping_id}",
    response_model=ColumnMappingResponse,
    status_code=status.HTTP_200_OK,
)
def get_mapping(
    mapping_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a column mapping by ID."""
    mapping = column_mapping_service.get_column_mapping(db=db, mapping_id=mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Column mapping not found",
        )
    return mapping


@router.patch(
    "/{mapping_id}",
    response_model=ColumnMappingResponse,
    status_code=status.HTTP_200_OK,
)
def update_mapping(
    mapping_id: UUID,
    mapping_data: ColumnMappingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing column mapping."""
    mapping = column_mapping_service.get_column_mapping(db=db, mapping_id=mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Column mapping not found",
        )
    return column_mapping_service.update_column_mapping(
        db=db,
        mapping=mapping,
        mapping_in=mapping_data,
    )


@router.delete(
    "/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_mapping(
    mapping_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a column mapping."""
    mapping = column_mapping_service.get_column_mapping(db=db, mapping_id=mapping_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Column mapping not found",
        )
    column_mapping_service.delete_column_mapping(db=db, mapping=mapping)
    return None