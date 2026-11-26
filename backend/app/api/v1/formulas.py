from typing import Any, Dict, List
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.services import formula_service

router = APIRouter(prefix="/api/v1/formulas", tags=["Formulas"])


@router.post(
    "/apply",
    status_code=status.HTTP_200_OK,
)
def apply_formula(
    formula: str,
    df_json: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a safe formula to a DataFrame (JSON format).

    Supported operations:
    - Column arithmetic: col1 * col2, col1 - col2, col1 + col2, col1 / col2
    - Number literals: col1 * 1.1, col2 - 10
    - Parentheses: (col1 + col2) * 0.1

    Never uses eval() - uses a safe recursive-descent parser instead.

    Example formulas:
    - "quantity * unit_price"  -> net revenue
    - "unit_price - discount"  -> discounted price
    - "quantity * unit_price * 0.1"  -> tax amount
    """
    import io

    try:
        df = pd.read_json(io.StringIO(df_json))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse DataFrame JSON: {exc}",
        )

    try:
        result = formula_service.apply_formula(df, formula)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Formula evaluation failed: {exc}",
        )

    return {
        "formula": formula,
        "result": result.tolist(),
        "result_dtype": str(result.dtype),
        "row_count": len(result),
    }


@router.get(
    "/supported-operations",
    status_code=status.HTTP_200_OK,
)
def supported_operations():
    """List supported formula operations."""
    return {
        "operations": [
            {
                "name": "add",
                "symbol": "+",
                "description": "Add two columns or a column and a number",
                "example": "col1 + col2",
            },
            {
                "name": "subtract",
                "symbol": "-",
                "description": "Subtract two columns or a column and a number",
                "example": "col1 - discount",
            },
            {
                "name": "multiply",
                "symbol": "*",
                "description": "Multiply two columns or a column and a number",
                "example": "quantity * unit_price",
            },
            {
                "name": "divide",
                "symbol": "/",
                "description": "Divide two columns or a column and a number",
                "example": "col1 / col2",
            },
        ],
        "features": [
            "Column name references",
            "Numeric literals",
            "Parentheses for grouping",
            "Operator precedence (*/ before +-)",
        ],
        "security": "No eval() used - safe recursive-descent parser",
    }