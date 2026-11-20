from uuid import uuid4

from fastapi import HTTPException, status

from app.core.branch_access import get_accessible_branch
from app.models import User


def make_user(*, role: str, branch_id=None):
    return User(
        id=uuid4(),
        employee_id="EMP-TEST",
        name="Test User",
        email="test@store.com",
        password_hash="hash",
        role=role,
        branch_id=branch_id,
        is_active=True,
    )


def test_admin_can_access_any_branch():
    admin = make_user(role="admin", branch_id=None)
    requested = uuid4()
    result = get_accessible_branch(requested_branch_id=requested, current_user=admin)
    assert result == requested


def test_manager_accesses_own_branch():
    branch_id = uuid4()
    manager = make_user(role="manager", branch_id=branch_id)
    result = get_accessible_branch(requested_branch_id=branch_id, current_user=manager)
    assert result == branch_id


def test_manager_cannot_access_other_branch():
    branch_a = uuid4()
    branch_b = uuid4()
    manager = make_user(role="manager", branch_id=branch_a)

    try:
        get_accessible_branch(requested_branch_id=branch_b, current_user=manager)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_403_FORBIDDEN


def test_employee_without_branch_raises_403():
    employee = make_user(role="employee", branch_id=None)

    try:
        get_accessible_branch(requested_branch_id=None, current_user=employee)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert "No branch assigned" in exc.detail
