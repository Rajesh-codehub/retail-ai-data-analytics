"""Validation service for uploaded files.

Validates uploaded CSV and Excel files against a column schema,
collecting all errors (by column first, then by row) instead of
stopping at the first error.
"""

import csv
import io
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.upload_file import UploadFile
from app.models.validation_issue import ValidationIssue
from app.schemas.validation import ColumnSchema, DatasetSchema


# ---------------------------------------------------------------------------
# Default schema for a "sales" dataset
# ---------------------------------------------------------------------------

DEFAULT_SALES_SCHEMA = DatasetSchema(
    name="sales",
    columns={
        "transaction_id": ColumnSchema(required=True, data_type="string"),
        "branch_id": ColumnSchema(required=True, data_type="string"),
        "customer_id": ColumnSchema(required=False, data_type="string"),
        "product_id": ColumnSchema(required=True, data_type="string"),
        "quantity": ColumnSchema(required=True, data_type="float", min_value=0),
        "unit_price": ColumnSchema(required=True, data_type="float", min_value=0),
        "transaction_date": ColumnSchema(required=True, data_type="date"),
        "payment_method": ColumnSchema(
            required=False,
            data_type="string",
            allowed_values=["cash", "card", "upi", "online"],
        ),
    },
    allow_extra_columns=False,
)

DEFAULT_INVENTORY_SCHEMA = DatasetSchema(
    name="inventory",
    columns={
        "branch_id": ColumnSchema(required=True, data_type="string"),
        "product_id": ColumnSchema(required=True, data_type="string"),
        "quantity_on_hand": ColumnSchema(required=True, data_type="float", min_value=0),
        "reorder_level": ColumnSchema(required=False, data_type="float", min_value=0),
    },
    allow_extra_columns=False,
)

DATASET_SCHEMAS: dict[str, DatasetSchema] = {
    "sales": DEFAULT_SALES_SCHEMA,
    "inventory": DEFAULT_INVENTORY_SCHEMA,
}


def get_schema(dataset_type: str | None) -> DatasetSchema | None:
    """Return the schema for a given dataset_type, or None if not defined."""
    if dataset_type is None:
        return None
    return DATASET_SCHEMAS.get(dataset_type.lower())


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_value(
    value: Any,
    col_schema: ColumnSchema,
    row_number: int,
    column_name: str,
) -> list[dict[str, Any]]:
    """Validate a single cell value against its column schema.

    Returns a list of issue dicts (may be empty).
    """
    issues: list[dict[str, Any]] = []

    # Required check
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if col_schema.required:
            issues.append({
                "row_number": row_number,
                "column_name": column_name,
                "issue_code": "REQUIRED_FIELD_MISSING",
                "message": f"Required column '{column_name}' is missing or empty in row {row_number}",
                "severity": "error",
            })
        return issues

    # Type check
    if col_schema.data_type:
        type_issue = _check_type(value, col_schema.data_type, row_number, column_name)
        if type_issue:
            issues.append(type_issue)
            return issues

    # Range check (numeric)
    if col_schema.data_type in ("float", "integer") and col_schema.min_value is not None:
        try:
            num_val = float(value)
            if num_val < col_schema.min_value:
                issues.append({
                    "row_number": row_number,
                    "column_name": column_name,
                    "issue_code": "VALUE_BELOW_MINIMUM",
                    "message": f"Column '{column_name}' value {num_val} is below minimum {col_schema.min_value} in row {row_number}",
                    "severity": "error",
                })
        except (ValueError, TypeError):
            pass

    if col_schema.data_type in ("float", "integer") and col_schema.max_value is not None:
        try:
            num_val = float(value)
            if num_val > col_schema.max_value:
                issues.append({
                    "row_number": row_number,
                    "column_name": column_name,
                    "issue_code": "VALUE_ABOVE_MAXIMUM",
                    "message": f"Column '{column_name}' value {num_val} is above maximum {col_schema.max_value} in row {row_number}",
                    "severity": "error",
                })
        except (ValueError, TypeError):
            pass

    # Allowed values check
    if col_schema.allowed_values is not None:
        if str(value).strip().lower() not in [str(v).strip().lower() for v in col_schema.allowed_values]:
            issues.append({
                "row_number": row_number,
                "column_name": column_name,
                "issue_code": "VALUE_NOT_ALLOWED",
                "message": f"Column '{column_name}' value '{value}' is not in allowed values {col_schema.allowed_values} in row {row_number}",
                "severity": "error",
            })

    return issues


def _check_type(
    value: Any,
    data_type: str,
    row_number: int,
    column_name: str,
) -> dict[str, Any] | None:
    """Check if a value matches the expected data type.

    Returns an issue dict if the type is wrong, or None if OK.
    """
    try:
        if data_type == "string":
            return None
        elif data_type == "integer":
            int(value)
        elif data_type == "float":
            float(value)
        elif data_type == "bool":
            if str(value).strip().lower() not in ("true", "false", "0", "1", "yes", "no"):
                return {
                    "row_number": row_number,
                    "column_name": column_name,
                    "issue_code": "INVALID_TYPE",
                    "message": f"Column '{column_name}' expects a boolean value in row {row_number}, got '{value}'",
                    "severity": "error",
                }
        elif data_type == "date":
            from datetime import datetime

            datetime.strptime(str(value).strip(), "%Y-%m-%d")
    except (ValueError, TypeError):
        return {
            "row_number": row_number,
            "column_name": column_name,
            "issue_code": "INVALID_TYPE",
            "message": f"Column '{column_name}' expects type '{data_type}' in row {row_number}, got '{value}'",
            "severity": "error",
        }
    return None
    return None


# ---------------------------------------------------------------------------
# Main validation entry point
# ---------------------------------------------------------------------------

def validate_upload_file(
    db: Session,
    upload_id: UUID,
    dataset_type: str | None = None,
) -> dict:
    """Validate an uploaded file against its dataset schema.

    Reads the stored file, validates column-by-column then row-by-row,
    collects ALL errors, stores them as ValidationIssue records, and
    updates the UploadFile status to 'validated' or 'failed'.

    Returns a dict with validation summary.
    """
    record = db.query(UploadFile).filter(UploadFile.id == upload_id).first()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )

    file_path = Path(record.storage_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file not found on disk",
        )

    effective_dataset_type = dataset_type or record.dataset_type
    schema = get_schema(effective_dataset_type)

    record.status = "validating"
    db.commit()

    all_issues: list[dict[str, Any]] = []

    try:
        ext = record.file_type.lower()

        if ext == "csv":
            _validate_csv(file_path, schema, all_issues)
        elif ext == "xlsx":
            _validate_excel(file_path, schema, all_issues)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation not supported for file type '{ext}'",
            )

    except HTTPException:
        record.status = "failed"
        record.error_message = "Validation error"
        db.commit()
        raise

    for issue in all_issues:
        db_issue = ValidationIssue(
            upload_file_id=record.id,
            row_number=issue["row_number"],
            column_name=issue["column_name"],
            issue_code=issue["issue_code"],
            message=issue["message"],
            severity=issue["severity"],
        )
        db.add(db_issue)

    if all_issues:
        record.status = "failed"
        error_count = sum(1 for i in all_issues if i["severity"] == "error")
        warning_count = sum(1 for i in all_issues if i["severity"] == "warning")
        record.error_message = (
            f"Validation failed: {error_count} error(s), {warning_count} warning(s)"
        )
    else:
        record.status = "validated"
        record.error_message = None

    db.commit()
    db.refresh(record)

    error_count = sum(1 for i in all_issues if i["severity"] == "error")
    warning_count = sum(1 for i in all_issues if i["severity"] == "warning")

    return {
        "upload_id": record.id,
        "status": record.status,
        "dataset_type": effective_dataset_type,
        "total_issues": len(all_issues),
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": all_issues,
    }


# ---------------------------------------------------------------------------
# Per-file-type validation
# ---------------------------------------------------------------------------

def _validate_csv(
    file_path: Path,
    schema: DatasetSchema | None,
    all_issues: list[dict[str, Any]],
) -> None:
    """Validate a CSV file. Appends issues to all_issues."""
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []

        if schema is not None:
            for col_name, col_schema in schema.columns.items():
                if col_schema.required and col_name not in header:
                    all_issues.append({
                        "row_number": 0,
                        "column_name": col_name,
                        "issue_code": "MISSING_COLUMN",
                        "message": f"Required column '{col_name}' is not present in the file header",
                        "severity": "error",
                    })

            if not schema.allow_extra_columns:
                for col_name in header:
                    if col_name not in schema.columns:
                        all_issues.append({
                            "row_number": 0,
                            "column_name": col_name,
                            "issue_code": "UNEXPECTED_COLUMN",
                            "message": f"Column '{col_name}' is not expected in the schema",
                            "severity": "warning",
                        })

        for row_num, row in enumerate(reader, start=2):
            if schema is not None:
                for col_name, col_schema in schema.columns.items():
                    value = row.get(col_name)
                    all_issues.extend(
                        _validate_value(value, col_schema, row_num, col_name)
                    )


def _validate_excel(
    file_path: Path,
    schema: DatasetSchema | None,
    all_issues: list[dict[str, Any]],
) -> None:
    """Validate an Excel file. Appends issues to all_issues."""
    df = pd.read_excel(file_path, engine="openpyxl")
    header = df.columns.tolist()

    if schema is not None:
        for col_name, col_schema in schema.columns.items():
            if col_schema.required and col_name not in header:
                all_issues.append({
                    "row_number": 0,
                    "column_name": col_name,
                    "issue_code": "MISSING_COLUMN",
                    "message": f"Required column '{col_name}' is not present in the file header",
                    "severity": "error",
                })

        if not schema.allow_extra_columns:
            for col_name in header:
                if col_name not in schema.columns:
                    all_issues.append({
                        "row_number": 0,
                        "column_name": col_name,
                        "issue_code": "UNEXPECTED_COLUMN",
                        "message": f"Column '{col_name}' is not expected in the schema",
                        "severity": "warning",
                    })

    for row_idx, row in df.iterrows():
        row_num = row_idx + 2
        if schema is not None:
            for col_name, col_schema in schema.columns.items():
                value = row.get(col_name)
                import math

                if isinstance(value, float) and math.isnan(value):
                    value = None
                all_issues.extend(
                    _validate_value(value, col_schema, row_num, col_name)
                )