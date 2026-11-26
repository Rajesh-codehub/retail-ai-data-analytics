from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.transformation_operation import (
    TransformationOperationCreate,
    TransformationOperationListResponse,
    TransformationOperationResponse,
    TransformationOperationUpdate,
    BUILTIN_OPERATIONS,
)
from app.services import transformation_operation_service

router = APIRouter(prefix="/api/v1/transformation-operations", tags=["Transformation Operations"])


@router.get(
    "/builtin",
    status_code=status.HTTP_200_OK,
)
def list_builtin_operations():
    """List all built-in transformation operations with their required config."""
    return BUILTIN_OPERATIONS


@router.post(
    "/",
    response_model=TransformationOperationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_operation(
    op_data: TransformationOperationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new transformation operation."""
    return transformation_operation_service.create_transformation_operation(
        db=db,
        op_in=op_data,
        created_by=current_user.id,
    )


@router.get(
    "/",
    response_model=TransformationOperationListResponse,
    status_code=status.HTTP_200_OK,
)
def list_operations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    operation_type: Optional[str] = Query(default=None),
    is_builtin: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List transformation operations with optional filters."""
    items, total = transformation_operation_service.get_transformation_operations(
        db=db,
        skip=skip,
        limit=limit,
        operation_type=operation_type,
        is_builtin=is_builtin,
    )
    return TransformationOperationListResponse(items=items, total=total)


@router.get(
    "/{op_id}",
    response_model=TransformationOperationResponse,
    status_code=status.HTTP_200_OK,
)
def get_operation(
    op_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a transformation operation by ID."""
    op = transformation_operation_service.get_transformation_operation(db=db, op_id=op_id)
    if not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transformation operation not found",
        )
    return op


@router.patch(
    "/{op_id}",
    response_model=TransformationOperationResponse,
    status_code=status.HTTP_200_OK,
)
def update_operation(
    op_id: UUID,
    op_data: TransformationOperationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing transformation operation."""
    op = transformation_operation_service.get_transformation_operation(db=db, op_id=op_id)
    if not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transformation operation not found",
        )
    return transformation_operation_service.update_transformation_operation(
        db=db,
        op=op,
        op_in=op_data,
    )


@router.delete(
    "/{op_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_operation(
    op_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a transformation operation."""
    op = transformation_operation_service.get_transformation_operation(db=db, op_id=op_id)
    if not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transformation operation not found",
        )
    transformation_operation_service.delete_transformation_operation(db=db, op=op)
    return None


@router.post(
    "/apply",
    status_code=status.HTTP_200_OK,
)
def apply_operations_endpoint(
    operations: List[Dict[str, Any]],
    df_json: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a list of transformation operations to a DataFrame (JSON format).

    This is a helper endpoint to test transformations before saving them.
    """
    import pandas as pd
    import io

    try:
        df = pd.read_json(io.StringIO(df_json))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse DataFrame JSON: {exc}",
        )

    # Validate all operations first
    for op in operations:
        op_type = op.get("operation_type", "")
        config = op.get("config", {})
        try:
            transformation_operation_service.validate_operation_config(op_type, config)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

    try:
        result_df = transformation_operation_service.apply_operations(df, operations)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {"result": result_df.to_dict(orient="records")}