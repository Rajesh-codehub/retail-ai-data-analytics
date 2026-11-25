import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.column_mapping import ColumnMapping
from app.models.user import User
from app.schemas.column_mapping import ColumnMappingCreate, ColumnMappingUpdate
from app.services import column_mapping_service


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


def make_mapping_create(dataset_type: str = "sales", source_column: str = "col1", target_field: str = "sku", is_template: bool = False):
    return ColumnMappingCreate(
        dataset_type=dataset_type,
        source_column=source_column,
        target_field=target_field,
        is_template=is_template,
    )


# ---------------------------------------------------------------------------
# create_column_mapping Tests
# ---------------------------------------------------------------------------


def test_create_column_mapping_success(db_session):
    user = make_user(db_session)
    mapping_in = make_mapping_create("sales", "product_sku", "sku")

    mapping = column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=mapping_in,
        created_by=user.id,
    )

    assert mapping.id is not None
    assert mapping.dataset_type == "sales"
    assert mapping.source_column == "product_sku"
    assert mapping.target_field == "sku"
    assert mapping.created_by == user.id


def test_create_column_mapping_unknown_dataset_type(db_session):
    user = make_user(db_session)
    mapping_in = make_mapping_create("unknown_dataset", "col1", "sku")

    with pytest.raises(HTTPException) as exc:
        column_mapping_service.create_column_mapping(
            db=db_session,
            mapping_in=mapping_in,
            created_by=user.id,
        )
    assert exc.value.status_code == 400


def test_create_column_mapping_duplicate_source(db_session):
    user = make_user(db_session)
    mapping_in = make_mapping_create("sales", "col1", "sku")

    column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=mapping_in,
        created_by=user.id,
    )

    with pytest.raises(HTTPException) as exc:
        column_mapping_service.create_column_mapping(
            db=db_session,
            mapping_in=mapping_in,
            created_by=user.id,
        )
    assert exc.value.status_code == 409


def test_create_column_mapping_duplicate_target(db_session):
    user = make_user(db_session)
    column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=make_mapping_create("sales", "col1", "sku"),
        created_by=user.id,
    )

    with pytest.raises(HTTPException) as exc:
        column_mapping_service.create_column_mapping(
            db=db_session,
            mapping_in=make_mapping_create("sales", "col2", "sku"),
            created_by=user.id,
        )
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# get_column_mapping / get_column_mappings Tests
# ---------------------------------------------------------------------------


def test_get_column_mapping_success(db_session):
    user = make_user(db_session)
    mapping = column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=make_mapping_create("sales", "col1", "sku"),
        created_by=user.id,
    )

    fetched = column_mapping_service.get_column_mapping(db=db_session, mapping_id=mapping.id)
    assert fetched is not None
    assert fetched.id == mapping.id
    assert fetched.source_column == "col1"


def test_get_column_mapping_not_found(db_session):
    result = column_mapping_service.get_column_mapping(db=db_session, mapping_id=uuid.uuid4())
    assert result is None


def test_get_column_mappings_list(db_session):
    user = make_user(db_session)
    column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=make_mapping_create("sales", "col1", "sku"),
        created_by=user.id,
    )
    column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=make_mapping_create("sales", "col2", "branch"),
        created_by=user.id,
    )
    column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=make_mapping_create("inventory", "col3", "sku"),
        created_by=user.id,
    )

    items, total = column_mapping_service.get_column_mappings(db=db_session)
    assert total == 3
    assert len(items) == 3

    items, total = column_mapping_service.get_column_mappings(db=db_session, dataset_type="sales")
    assert total == 2
    assert len(items) == 2

    items, total = column_mapping_service.get_column_mappings(db=db_session, dataset_type="inventory")
    assert total == 1
    assert len(items) == 1


# ---------------------------------------------------------------------------
# update_column_mapping Tests
# ---------------------------------------------------------------------------


def test_update_column_mapping_success(db_session):
    user = make_user(db_session)
    mapping = column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=make_mapping_create("sales", "col1", "sku"),
        created_by=user.id,
    )

    updated = column_mapping_service.update_column_mapping(
        db=db_session,
        mapping=mapping,
        mapping_in=ColumnMappingUpdate(target_field="product_sku"),
    )

    assert updated.target_field == "product_sku"
    assert updated.source_column == "col1"  # unchanged


def test_update_column_mapping_duplicate_target(db_session):
    user = make_user(db_session)
    mapping1 = column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=make_mapping_create("sales", "col1", "sku"),
        created_by=user.id,
    )
    mapping2 = column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=make_mapping_create("sales", "col2", "branch"),
        created_by=user.id,
    )

    with pytest.raises(HTTPException) as exc:
        column_mapping_service.update_column_mapping(
            db=db_session,
            mapping=mapping1,
            mapping_in=ColumnMappingUpdate(target_field="branch"),
        )
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# delete_column_mapping Tests
# ---------------------------------------------------------------------------


def test_delete_column_mapping_success(db_session):
    user = make_user(db_session)
    mapping = column_mapping_service.create_column_mapping(
        db=db_session,
        mapping_in=make_mapping_create("sales", "col1", "sku"),
        created_by=user.id,
    )

    column_mapping_service.delete_column_mapping(db=db_session, mapping=mapping)

    result = column_mapping_service.get_column_mapping(db=db_session, mapping_id=mapping.id)
    assert result is None