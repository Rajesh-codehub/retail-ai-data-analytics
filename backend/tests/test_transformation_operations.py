import uuid
import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.user import User
from app.models.transformation_operation import TransformationOperation
from app.schemas.transformation_operation import TransformationOperationCreate
from app.services import transformation_operation_service


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def make_user(db_session, *, role: str = "admin", branch_id=None):
    user = User(
        id=uuid.uuid4(),
        employee_id=f"EMP-{uuid.uuid4().hex[:8]}",
        name="Test User",
        email=f"test_{uuid.uuid4().hex[:8]}@store.com",
        password_hash="hash",
        role=role,
        branch_id=branch_id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Pure operation function tests
# ---------------------------------------------------------------------------


def test_op_rename():
    df = pd.DataFrame({"old_col": [1, 2, 3], "other": ["a", "b", "c"]})
    result = transformation_operation_service.op_rename(
        df, {"old_name": "old_col", "new_name": "new_col"}
    )
    assert "new_col" in result.columns
    assert "old_col" not in result.columns
    assert list(result["new_col"]) == [1, 2, 3]


def test_op_rename_missing_column():
    df = pd.DataFrame({"col1": [1, 2]})
    with pytest.raises(ValueError) as exc:
        transformation_operation_service.op_rename(
            df, {"old_name": "nonexistent", "new_name": "new_col"}
        )
    assert "not found" in str(exc.value)


def test_op_cast_to_integer():
    df = pd.DataFrame({"num": ["1", "2", "3"]})
    result = transformation_operation_service.op_cast(
        df, {"column": "num", "to_type": "integer"}
    )
    assert result["num"].dtype == "Int64"
    assert list(result["num"]) == [1, 2, 3]


def test_op_cast_to_float():
    df = pd.DataFrame({"num": ["1.5", "2.5", "3.5"]})
    result = transformation_operation_service.op_cast(
        df, {"column": "num", "to_type": "float"}
    )
    assert result["num"].dtype == "float64"
    assert list(result["num"]) == [1.5, 2.5, 3.5]


def test_op_cast_invalid_type():
    df = pd.DataFrame({"col": ["a", "b"]})
    with pytest.raises(ValueError) as exc:
        transformation_operation_service.op_cast(
            df, {"column": "col", "to_type": "invalid_type"}
        )
    assert "Invalid cast type" in str(exc.value)


def test_op_strip():
    df = pd.DataFrame({"text": ["  hello  ", "  world  "]})
    result = transformation_operation_service.op_strip(
        df, {"column": "text"}
    )
    assert list(result["text"]) == ["hello", "world"]


def test_op_lowercase():
    df = pd.DataFrame({"text": ["HELLO", "World"]})
    result = transformation_operation_service.op_lowercase(
        df, {"column": "text"}
    )
    assert list(result["text"]) == ["hello", "world"]


def test_op_parse_date():
    df = pd.DataFrame({"date": ["2026-01-15", "2026-01-16"]})
    result = transformation_operation_service.op_parse_date(
        df, {"column": "date", "format": "%Y-%m-%d"}
    )
    assert str(result["date"].iloc[0]) == "2026-01-15 00:00:00"


# ---------------------------------------------------------------------------
# apply_operations tests
# ---------------------------------------------------------------------------


def test_apply_operations_chain():
    df = pd.DataFrame({"old_col": ["  HELLO  ", "  WORLD  "], "num": ["1", "2"]})
    operations = [
        {"operation_type": "rename", "config": {"old_name": "old_col", "new_name": "text"}},
        {"operation_type": "strip", "config": {"column": "text"}},
        {"operation_type": "lowercase", "config": {"column": "text"}},
        {"operation_type": "cast", "config": {"column": "num", "to_type": "integer"}},
    ]
    result = transformation_operation_service.apply_operations(df, operations)
    assert list(result["text"]) == ["hello", "world"]
    assert list(result["num"]) == [1, 2]


def test_apply_operations_unknown_type():
    df = pd.DataFrame({"col": [1, 2]})
    with pytest.raises(ValueError) as exc:
        transformation_operation_service.apply_operations(
            df, [{"operation_type": "unknown_op", "config": {}}]
        )
    assert "Unknown operation type" in str(exc.value)


# ---------------------------------------------------------------------------
# validate_operation_config tests
# ---------------------------------------------------------------------------


def test_validate_operation_config_valid():
    transformation_operation_service.validate_operation_config(
        "rename", {"old_name": "a", "new_name": "b"}
    )


def test_validate_operation_config_missing_field():
    with pytest.raises(ValueError) as exc:
        transformation_operation_service.validate_operation_config(
            "rename", {"old_name": "a"}
        )
    assert "Missing required config fields" in str(exc.value)


def test_validate_operation_config_unknown_type():
    with pytest.raises(ValueError) as exc:
        transformation_operation_service.validate_operation_config(
            "unknown_type", {}
        )
    assert "Unknown operation type" in str(exc.value)


def test_validate_operation_config_cast_invalid_type():
    with pytest.raises(ValueError) as exc:
        transformation_operation_service.validate_operation_config(
            "cast", {"column": "a", "to_type": "bad_type"}
        )
    assert "Invalid cast type" in str(exc.value)


# ---------------------------------------------------------------------------
# Service CRUD tests
# ---------------------------------------------------------------------------


def test_create_operation_success(db_session):
    user = make_user(db_session)
    op_in = TransformationOperationCreate(
        name="Strip whitespace",
        operation_type="strip",
        config={"column": "text"},
        is_builtin=False,
    )

    op = transformation_operation_service.create_transformation_operation(
        db=db_session,
        op_in=op_in,
        created_by=user.id,
    )

    assert op.id is not None
    assert op.name == "Strip whitespace"
    assert op.operation_type == "strip"
    assert op.config == {"column": "text"}
    assert op.created_by == user.id


def test_create_operation_unknown_type(db_session):
    user = make_user(db_session)
    op_in = TransformationOperationCreate(
        name="Bad op",
        operation_type="unknown_type",
        config={},
    )

    with pytest.raises(HTTPException) as exc:
        transformation_operation_service.create_transformation_operation(
            db=db_session,
            op_in=op_in,
            created_by=user.id,
        )
    assert exc.value.status_code == 400


def test_create_operation_duplicate_name(db_session):
    user = make_user(db_session)
    op_in = TransformationOperationCreate(
        name="My Op",
        operation_type="strip",
        config={"column": "text"},
    )

    transformation_operation_service.create_transformation_operation(
        db=db_session,
        op_in=op_in,
        created_by=user.id,
    )

    with pytest.raises(HTTPException) as exc:
        transformation_operation_service.create_transformation_operation(
            db=db_session,
            op_in=op_in,
            created_by=user.id,
        )
    assert exc.value.status_code == 409


def test_get_operation_success(db_session):
    user = make_user(db_session)
    op = transformation_operation_service.create_transformation_operation(
        db=db_session,
        op_in=TransformationOperationCreate(
            name="Test Op",
            operation_type="lowercase",
            config={"column": "text"},
        ),
        created_by=user.id,
    )

    fetched = transformation_operation_service.get_transformation_operation(
        db=db_session, op_id=op.id
    )
    assert fetched is not None
    assert fetched.id == op.id


def test_get_operation_not_found(db_session):
    result = transformation_operation_service.get_transformation_operation(
        db=db_session, op_id=uuid.uuid4()
    )
    assert result is None


def test_list_operations(db_session):
    user = make_user(db_session)
    for i in range(3):
        transformation_operation_service.create_transformation_operation(
            db=db_session,
            op_in=TransformationOperationCreate(
                name=f"Op {i}",
                operation_type="strip",
                config={"column": f"col{i}"},
            ),
            created_by=user.id,
        )

    items, total = transformation_operation_service.get_transformation_operations(
        db=db_session
    )
    assert total == 3
    assert len(items) == 3


def test_list_operations_filter_by_type(db_session):
    user = make_user(db_session)
    transformation_operation_service.create_transformation_operation(
        db=db_session,
        op_in=TransformationOperationCreate(
            name="Strip Op",
            operation_type="strip",
            config={"column": "text"},
        ),
        created_by=user.id,
    )
    transformation_operation_service.create_transformation_operation(
        db=db_session,
        op_in=TransformationOperationCreate(
            name="Cast Op",
            operation_type="cast",
            config={"column": "num", "to_type": "integer"},
        ),
        created_by=user.id,
    )

    items, total = transformation_operation_service.get_transformation_operations(
        db=db_session, operation_type="strip"
    )
    assert total == 1
    assert items[0].name == "Strip Op"


def test_update_operation_success(db_session):
    user = make_user(db_session)
    op = transformation_operation_service.create_transformation_operation(
        db=db_session,
        op_in=TransformationOperationCreate(
            name="Original",
            operation_type="strip",
            config={"column": "text"},
        ),
        created_by=user.id,
    )

    from app.schemas.transformation_operation import TransformationOperationUpdate
    updated = transformation_operation_service.update_transformation_operation(
        db=db_session,
        op=op,
        op_in=TransformationOperationUpdate(name="Updated Name"),
    )
    assert updated.name == "Updated Name"


def test_delete_operation_success(db_session):
    user = make_user(db_session)
    op = transformation_operation_service.create_transformation_operation(
        db=db_session,
        op_in=TransformationOperationCreate(
            name="To Delete",
            operation_type="strip",
            config={"column": "text"},
        ),
        created_by=user.id,
    )

    transformation_operation_service.delete_transformation_operation(
        db=db_session, op=op
    )

    result = transformation_operation_service.get_transformation_operation(
        db=db_session, op_id=op.id
    )
    assert result is None