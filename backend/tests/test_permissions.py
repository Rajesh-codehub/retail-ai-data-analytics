from uuid import uuid4

from fastapi import HTTPException, status

from app.core.permissions import require_role
from app.models import User


def make_user(*, role: str):
    return User(
        id=uuid4(),
        employee_id="EMP-TEST",
        name="Test User",
        email="test@store.com",
        password_hash="hash",
        role=role,
        branch_id=None,
        is_active=True,
    )


def test_require_role_allows_admin():
    admin = make_user(role="admin")
    checker = require_role("admin")
    result = checker(current_user=admin)
    assert result == admin


def test_require_role_blocks_employee():
    employee = make_user(role="employee")
    checker = require_role("admin")

    try:
        checker(current_user=employee)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == status.HTTP_403_FORBIDDEN


def test_require_role_allows_multiple_roles():
    manager = make_user(role="manager")
    checker = require_role("admin", "manager")
    result = checker(current_user=manager)
    assert result == manager
