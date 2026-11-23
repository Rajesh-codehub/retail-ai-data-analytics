"""Data quality profiling service.

Computes null rates, distinct counts, min/max/avg for numeric columns,
and histograms/frequency distributions for categorical columns.
"""

from collections import Counter
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.upload_file import UploadFile


def profile_upload_file(
    db: Session,
    upload_id: UUID,
) -> dict:
    """Profile an uploaded file and compute data quality metrics.

    Returns a dict with per-column profiling results including:
    - null_count, null_rate
    - distinct_count
    - min, max, avg (for numeric columns)
    - top_values histogram (for categorical columns)
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

    ext = record.file_type.lower()

    try:
        if ext == "csv":
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        elif ext == "xlsx":
            df = pd.read_excel(file_path, engine="openpyxl", dtype=str)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Profiling not supported for file type '{ext}'",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file for profiling: {exc}",
        ) from exc

    total_rows = len(df)
    columns = df.columns.tolist()

    profile = {
        "upload_id": str(record.id),
        "original_filename": record.original_filename,
        "file_type": record.file_type,
        "total_rows": total_rows,
        "total_columns": len(columns),
        "columns": [],
    }

    for col_name in columns:
        col_profile = _profile_column(df[col_name], col_name, total_rows)
        profile["columns"].append(col_profile)

    return profile


def _profile_column(
    series: pd.Series,
    col_name: str,
    total_rows: int,
) -> dict[str, Any]:
    """Profile a single column and return quality metrics."""
    null_count = int(series.isna().sum() + (series == "").sum())
    null_rate = round(null_count / total_rows, 4) if total_rows > 0 else 0.0
    # Exclude empty strings from distinct count (they're nulls, not values)
    non_empty = series[(series.notna()) & (series != "")]
    distinct_count = int(non_empty.nunique())

    col_profile: dict[str, Any] = {
        "name": col_name,
        "null_count": null_count,
        "null_rate": null_rate,
        "distinct_count": distinct_count,
    }

    # Try to detect numeric column
    # Treat empty strings as NaN for numeric detection
    cleaned_series = series.replace("", pd.NA)
    numeric_series = pd.to_numeric(cleaned_series, errors="coerce")
    non_null_numeric = numeric_series.dropna()
    series_non_null = cleaned_series.dropna()

    if len(non_null_numeric) > 0 and len(non_null_numeric) == len(series_non_null):
        # Column is fully numeric
        col_profile["data_type"] = "numeric"
        col_profile["min"] = float(non_null_numeric.min())
        col_profile["max"] = float(non_null_numeric.max())
        col_profile["avg"] = round(float(non_null_numeric.mean()), 4)
    else:
        # Categorical column
        col_profile["data_type"] = "categorical"
        # Top 10 most frequent values
        counter = Counter(series.dropna().astype(str))
        top_values = counter.most_common(10)
        col_profile["top_values"] = [
            {"value": val, "count": count} for val, count in top_values
        ]

    return col_profile