from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.branch_access import get_accessible_branch
from app.db.database import get_db
from app.models import Transaction, User
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/transactions")
def get_transactions(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    accessible_branch: UUID | None = Depends(get_accessible_branch),
):
    query = db.query(Transaction)

    if accessible_branch is not None:
        query = query.filter(
            Transaction.branch_id == accessible_branch
        )

    return query.limit(100).all()