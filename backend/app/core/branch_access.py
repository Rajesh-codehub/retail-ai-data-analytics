from uuid import UUID

from fastapi import Depends, HTTPException, status

from app.api.v1.auth import get_current_user
from app.models import User


def get_accessible_branch(
    requested_branch_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
) -> UUID | None:

    # Admin can access any branch.
    if current_user.role == "admin":
        return requested_branch_id

    # Non-admin users must have an assigned branch.
    if current_user.branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No branch assigned to this user",
        )

    # Reject attempts to access another branch.
    if (
        requested_branch_id is not None
        and requested_branch_id != current_user.branch_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access this branch",
        )

    return current_user.branch_id