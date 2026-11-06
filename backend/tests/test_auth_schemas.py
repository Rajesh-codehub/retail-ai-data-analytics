import uuid
import pytest
from datetime import datetime
from pydantic import ValidationError
from app.schemas.auth import UserCreate, UserLogin, UserResponse, UserUpdate


def test_valid_user_creation():
    """Test that a valid user creation payload passes validation."""
    data = {
        "employee_id": "EMP-001",
        "name": "Rajesh Sammingi",
        "email": "rajesh@store.com",
        "password": "securepassword123",
        "role": "admin",
        "branch_id": uuid.uuid4()
    }
    user = UserCreate(**data)
    assert user.employee_id == "EMP-001"
    assert user.role == "admin"


def test_invalid_email_rejected():
    """Test that an invalid email format raises a ValidationError."""
    data = {
        "employee_id": "EMP-002",
        "name": "Priya Reddy",
        "email": "invalid-email-format",
        "password": "securepassword123",
        "role": "employee"
    }
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(**data)
    assert "email" in str(exc_info.value)


def test_short_password_rejected():
    """Test that a password shorter than 8 characters is rejected."""
    data = {
        "employee_id": "EMP-003",
        "name": "Amit Kumar",
        "email": "amit@store.com",
        "password": "short",  # Less than 8 chars
        "role": "manager"
    }
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(**data)
    assert "password" in str(exc_info.value)


def test_invalid_role_rejected():
    """Test that a role outside the allowed literal values is rejected."""
    data = {
        "employee_id": "EMP-004",
        "name": "Sneha Gupta",
        "email": "sneha@store.com",
        "password": "securepassword123",
        "role": "superadmin"  # Not in ["admin", "manager", "employee"]
    }
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(**data)
    assert "role" in str(exc_info.value)


def test_valid_login():
    """Test that a valid login payload passes validation."""
    data = {
        "email": "rajesh@store.com",
        "password": "securepassword123"
    }
    login = UserLogin(**data)
    assert login.email == "rajesh@store.com"


def test_user_response_excludes_password():
    """Test that UserResponse correctly parses from an ORM-like object and excludes password hashes."""
    
    # Mock a database User model instance
    class MockDBUser:
        def __init__(self):
            self.id = uuid.uuid4()
            self.employee_id = "EMP-001"
            self.name = "Rajesh Sammingi"
            self.email = "rajesh@store.com"
            self.password_hash = "$2b$12$secret_hashed_password"  # Should NOT appear in response
            self.role = "admin"
            self.branch_id = uuid.uuid4()
            self.is_active = True
            self.created_at = datetime.utcnow()

    db_user = MockDBUser()
    response = UserResponse.model_validate(db_user)

    # Verify fields populated correctly
    assert response.employee_id == db_user.employee_id
    assert response.email == db_user.email
    assert response.role == "admin"
    
    # Verify password or password_hash is not part of UserResponse schema fields
    response_dict = response.model_dump()
    assert "password" not in response_dict
    assert "password_hash" not in response_dict


def test_partial_user_update():
    """Test that UserUpdate allows partial fields and correctly isolates unset fields."""
    # Only updating name and is_active
    update_data = {
        "name": "Updated Name",
        "is_active": False
    }
    update_schema = UserUpdate(**update_data)
    
    dumped = update_schema.model_dump(exclude_unset=True)
    
    assert dumped == {"name": "Updated Name", "is_active": False}
    assert "email" not in dumped
    assert "role" not in dumped
    assert "branch_id" not in dumped