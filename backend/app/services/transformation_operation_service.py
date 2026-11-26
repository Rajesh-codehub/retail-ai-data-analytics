"""Transformation operation service.

Builds a whitelist of operations (rename, cast, strip, lowercase, parse date)
that can be applied to DataFrames using pandas. Never uses eval.
Each operation is a pure, unit-tested function.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from uuid import UUID

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.transformation_operation import TransformationOperation
from app.schemas.transformation_operation import (
    TransformationOperationCreate,
    TransformationOperationUpdate,
    BUILTIN_OPERATIONS,
)


# ---------------------------------------------------------------------------
# Pure transformation functions (applied to DataFrames)
# ---------------------------------------------------------------------------

def op_rename(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """Rename a column."""
    old_name = config["old_name"]
    new_name = config["new_name"]
    if old_name not in df.columns:
        raise ValueError(f"Column '{old_name}' not found")
    df = df.rename(columns={old_name: new_name})
    return df


def op_cast(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """Cast a column to a different type."""
    column = config["column"]
    to_type = config["to_type"]
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")

    allowed_types = ["string", "integer", "float", "date", "bool"]
    if to_type not in allowed_types:
        raise ValueError(f"Invalid cast type '{to_type}'. Allowed: {allowed_types}")

    if to_type == "string":
        df[column] = df[column].astype(str)
    elif to_type == "integer":
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
    elif to_type == "float":
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("float64")
    elif to_type == "date":
        df[column] = pd.to_datetime(df[column], errors="coerce").dt.date
    elif to_type == "bool":
        df[column] = df[column].map({"true": True, "false": False, "1": True, "0": False,
                                     "yes": True, "no": False}).astype("boolean")
    return df


def op_strip(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """Strip whitespace from a string column."""
    column = config["column"]
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    df[column] = df[column].astype(str).str.strip()
    return df


def op_lowercase(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """Convert a string column to lowercase."""
    column = config["column"]
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    df[column] = df[column].astype(str).str.lower()
    return df


def op_parse_date(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """Parse a column as dates using the given format string."""
    column = config["column"]
    fmt = config["format"]
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found")
    df[column] = pd.to_datetime(df[column], format=fmt, errors="coerce")
    return df


OPERATION_FUNCTIONS: dict[str, Callable] = {
    "rename": op_rename,
    "cast": op_cast,
    "strip": op_strip,
    "lowercase": op_lowercase,
    "parse_date": op_parse_date,
}


def apply_operations(df: pd.DataFrame, operations: List[Dict[str, Any]]) -> pd.DataFrame:
    """Apply a list of transformation operations to a DataFrame.

    Each operation dict must have 'operation_type' and 'config' keys.
    Unknown operation types raise ValueError.
    """
    for op in operations:
        op_type = op["operation_type"]
        config = op.get("config", {})

        if op_type not in OPERATION_FUNCTIONS:
            raise ValueError(f"Unknown operation type '{op_type}'")

        df = OPERATION_FUNCTIONS[op_type](df, config)

    return df


def validate_operation_config(operation_type: str, config: Dict[str, Any]) -> None:
    """Validate that an operation config contains all required fields."""
    if operation_type not in BUILTIN_OPERATIONS:
        raise ValueError(f"Unknown operation type '{operation_type}'")

    required = BUILTIN_OPERATIONS[operation_type]["required_config"]
    missing = [f for f in required if f not in config]
    if missing:
        raise ValueError(f"Missing required config fields: {', '.join(missing)}")

    if operation_type == "cast" and "to_type" in config:
        allowed_types = BUILTIN_OPERATIONS["cast"]["allowed_types"]
        if config["to_type"] not in allowed_types:
            raise ValueError(
                f"Invalid cast type '{config['to_type']}'. Allowed: {allowed_types}"
            )


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

def create_transformation_operation(
    db: Session,
    op_in: TransformationOperationCreate,
    created_by: UUID,
) -> TransformationOperation:
    """Create a new transformation operation."""
    op_type = op_in.operation_type.lower()

    if op_type not in BUILTIN_OPERATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown operation type '{op_in.operation_type}'",
        )

    try:
        validate_operation_config(op_type, op_in.config)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    existing = (
        db.query(TransformationOperation)
        .filter(TransformationOperation.name == op_in.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Operation '{op_in.name}' already exists",
        )

    op = TransformationOperation(
        name=op_in.name,
        operation_type=op_type,
        config=op_in.config,
        is_builtin=op_in.is_builtin,
        created_by=created_by,
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return op


def get_transformation_operation(
    db: Session,
    op_id: UUID,
) -> Optional[TransformationOperation]:
    """Get a transformation operation by ID."""
    return db.query(TransformationOperation).filter(TransformationOperation.id == op_id).first()


def get_transformation_operations(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    operation_type: Optional[str] = None,
    is_builtin: Optional[bool] = None,
) -> tuple[list[TransformationOperation], int]:
    """List transformation operations with optional filters."""
    query = db.query(TransformationOperation)

    if operation_type:
        query = query.filter(TransformationOperation.operation_type == operation_type.lower())
    if is_builtin is not None:
        query = query.filter(TransformationOperation.is_builtin == is_builtin)

    total = query.count()
    items = (
        query.order_by(TransformationOperation.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def update_transformation_operation(
    db: Session,
    op: TransformationOperation,
    op_in: TransformationOperationUpdate,
) -> TransformationOperation:
    """Update an existing transformation operation."""
    update_data = op_in.model_dump(exclude_unset=True)

    if "operation_type" in update_data:
        new_type = update_data["operation_type"].lower()
        if new_type not in BUILTIN_OPERATIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown operation type '{new_type}'",
            )
        update_data["operation_type"] = new_type

    if "config" in update_data and "operation_type" in update_data:
        try:
            validate_operation_config(update_data["operation_type"], update_data["config"])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
    elif "config" in update_data and op.operation_type:
        try:
            validate_operation_config(op.operation_type, update_data["config"])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

    if "name" in update_data:
        existing = (
            db.query(TransformationOperation)
            .filter(TransformationOperation.name == update_data["name"])
            .filter(TransformationOperation.id != op.id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Operation '{update_data['name']}' already exists",
            )

    for field, value in update_data.items():
        setattr(op, field, value)

    db.commit()
    db.refresh(op)
    return op


def delete_transformation_operation(
    db: Session,
    op: TransformationOperation,
) -> None:
    """Delete a transformation operation."""
    db.delete(op)
    db.commit()