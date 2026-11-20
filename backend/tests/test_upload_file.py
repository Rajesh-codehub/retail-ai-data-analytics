import hashlib
import io
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import openpyxl
import pytest
from fastapi import HTTPException, UploadFile as FastAPIUploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Replace `app.services.upload_service` with your actual service module path
from app.db.base import Base  # or wherever your declarative Base is defined
from app.models.upload_file import UploadFile
from app.models.user import User
from app.models.branch import Branch
import app.services.upload_service as upload_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


@pytest.fixture
def upload_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    upload_dir = tmp_path / "uploads"
    max_size = 1024  # 1 KB for fast boundary/chunk tests
    chunk_size = 256
    allowed_exts = {".csv", ".xlsx"}

    monkeypatch.setattr(upload_service, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(upload_service, "MAX_FILE_SIZE", max_size)
    monkeypatch.setattr(upload_service, "CHUNK_SIZE", chunk_size)
    monkeypatch.setattr(upload_service, "ALLOWED_EXTENSIONS", allowed_exts)

    return SimpleNamespace(
        upload_dir=upload_dir,
        max_size=max_size,
        chunk_size=chunk_size,
        allowed_exts=allowed_exts,
    )


def make_user(
    *,
    user_id: Optional[uuid.UUID] = None,
    role: Optional[str] = "employee",
    branch_id: Optional[uuid.UUID] = None,
):
    return SimpleNamespace(
        id=user_id or uuid.uuid4(),
        role=role,
        branch_id=branch_id,
    )


def make_upload_file(filename: Optional[str], content: bytes) -> FastAPIUploadFile:
    return FastAPIUploadFile(filename=filename, file=io.BytesIO(content))


def seed_user_in_db(
    db,
    *,
    user_id: uuid.UUID,
    role: str = "employee",
    branch_id: Optional[uuid.UUID] = None,
) -> User:
    """Create an actual User row in the DB so FK constraints are satisfied."""
    # Ensure branch exists first if referenced
    if branch_id is not None:
        seed_branch_in_db(db, branch_id=branch_id)
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    user = User(
        id=user_id,
        employee_id=f"EMP-{str(user_id)[:8]}",
        name="Seed User",
        email=f"seed_{str(user_id)[:8]}@store.com",
        password_hash="hash",
        role=role,
        branch_id=branch_id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def seed_branch_in_db(
    db,
    *,
    branch_id: uuid.UUID,
    branch_code: Optional[str] = None,
    branch_name: str = "Seed Branch",
    city: str = "Seed City",
) -> Branch:
    """Create an actual Branch row in the DB so FK constraints are satisfied."""
    existing = db.query(Branch).filter(Branch.id == branch_id).first()
    if existing:
        return existing
    if branch_code is None:
        branch_code = f"SEED-{str(branch_id)[:8]}"
    branch = Branch(
        id=branch_id,
        branch_code=branch_code,
        branch_name=branch_name,
        city=city,
    )
    db.add(branch)
    db.flush()
    return branch


def seed_upload(
    db,
    *,
    uploaded_by: uuid.UUID,
    branch_id: Optional[uuid.UUID] = None,
    original_filename: str = "data.csv",
    file_type: str = "csv",
    file_size: int = 10,
    status: str = "uploaded",
    dataset_type: Optional[str] = "sales",
    uploaded_at: Optional[datetime] = None,
) -> UploadFile:
    # Ensure parent records exist for foreign key constraints
    seed_user_in_db(db, user_id=uploaded_by, role="employee", branch_id=branch_id)
    if branch_id is not None:
        seed_branch_in_db(db, branch_id=branch_id)

    record = UploadFile(
        id=uuid.uuid4(),
        uploaded_by=uploaded_by,
        original_filename=original_filename,
        storage_path=f"/tmp/{uuid.uuid4()}.{file_type}",
        file_type=file_type,
        file_size=file_size,
        status=status,
        dataset_type=dataset_type,
        branch_id=branch_id,
        file_hash=hashlib.sha256(original_filename.encode()).hexdigest(),
        uploaded_at=uploaded_at or datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# 1. _resolve_branch_id Tests
# ---------------------------------------------------------------------------


def test_resolve_branch_id_admin_uses_requested_branch():
    admin = make_user(role="admin", branch_id=uuid.uuid4())
    target_branch = uuid.uuid4()
    assert upload_service._resolve_branch_id(admin, target_branch) == target_branch


def test_resolve_branch_id_admin_falls_back_to_user_branch():
    user_branch = uuid.uuid4()
    admin = make_user(role="ADMIN", branch_id=user_branch)
    assert upload_service._resolve_branch_id(admin, None) == user_branch


def test_resolve_branch_id_non_admin_matching_branch():
    branch = uuid.uuid4()
    mgr = make_user(role="manager", branch_id=branch)
    assert upload_service._resolve_branch_id(mgr, branch) == branch
    assert upload_service._resolve_branch_id(mgr, None) == branch


def test_resolve_branch_id_non_admin_branch_none_allows_requested():
    emp = make_user(role="employee", branch_id=None)
    assert upload_service._resolve_branch_id(emp, uuid.uuid4()) is None


def test_resolve_branch_id_non_admin_different_branch_raises_403():
    mgr = make_user(role="manager", branch_id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        upload_service._resolve_branch_id(mgr, uuid.uuid4())
    assert exc.value.status_code == 403
    assert "another branch" in exc.value.detail


@pytest.mark.parametrize("role", ["", None, "guest"])
def test_resolve_branch_id_unknown_or_empty_role_treated_as_non_admin(role):
    user = make_user(role=role, branch_id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        upload_service._resolve_branch_id(user, uuid.uuid4())
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# 2. save_upload_file Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,expected_ext,payload",
    [
        ("sales.csv", "csv", b"col1,col2\n1,2\n3,4\n"),
        ("Report.CsV", "csv", b"col1,col2\n1,2\n3,4\n"),
    ],
)
def test_save_upload_file_success_csv(db_session, upload_env, filename, expected_ext, payload):
    branch_id = uuid.uuid4()
    user = make_user(role="manager", branch_id=branch_id)
    seed_user_in_db(db_session, user_id=user.id, role=user.role, branch_id=user.branch_id)
    expected_hash = hashlib.sha256(payload).hexdigest()

    upload = make_upload_file(filename, payload)
    record = upload_service.save_upload_file(
        db=db_session,
        file=upload,
        current_user=user,
        dataset_type="  SaLeS  ",
        branch_id=branch_id,
    )

    assert record.id is not None
    assert record.uploaded_by == user.id
    assert record.original_filename == filename
    assert record.file_type == expected_ext
    assert record.file_size == len(payload)
    assert record.status == "uploaded"
    assert record.dataset_type == "sales"
    assert record.branch_id == branch_id
    assert record.file_hash == expected_hash
    assert Path(record.storage_path).exists()
    assert upload.file.closed


def test_save_upload_file_success_xlsx(db_session):
    branch_id = uuid.uuid4()
    user = make_user(role="manager", branch_id=branch_id)
    seed_user_in_db(db_session, user_id=user.id, role=user.role, branch_id=user.branch_id)
    upload = _make_excel_file("INVENTORY.XLSX", has_data=True)
    expected_hash = hashlib.sha256(upload.file.read()).hexdigest()
    upload.file.seek(0)

    record = upload_service.save_upload_file(
        db=db_session,
        file=upload,
        current_user=user,
        dataset_type="sales",
        branch_id=branch_id,
    )

    assert record.id is not None
    assert record.uploaded_by == user.id
    assert record.original_filename == "INVENTORY.XLSX"
    assert record.file_type == "xlsx"
    assert record.file_size > 0
    assert record.status == "uploaded"
    assert record.dataset_type == "sales"
    assert record.branch_id == branch_id
    assert record.file_hash == expected_hash
    assert Path(record.storage_path).exists()
    assert upload.file.closed


def test_save_upload_file_exact_max_size_succeeds(db_session, upload_env):
    user = make_user(role="employee")
    seed_user_in_db(db_session, user_id=user.id, role=user.role, branch_id=user.branch_id)
    # Build valid CSV: header + data rows filling up to max_size
    header = b"col1,col2\n"
    data = b"a" * (upload_env.max_size - len(header))
    payload = header + data

    record = upload_service.save_upload_file(
        db=db_session,
        file=make_upload_file("exact.csv", payload),
        current_user=user,
    )
    assert record.file_size == upload_env.max_size
    assert Path(record.storage_path).exists()


@pytest.mark.parametrize("bad_name", [None, ""])
def test_save_upload_file_missing_filename_raises_400(db_session, upload_env, bad_name):
    user = make_user(role="employee")
    with pytest.raises(HTTPException) as exc:
        upload_service.save_upload_file(
            db=db_session,
            file=make_upload_file(bad_name, b"data"),
            current_user=user,
        )
    assert exc.value.status_code == 400
    assert "Filename is missing" in exc.value.detail


@pytest.mark.parametrize("bad_file", ["malware.exe", "notes.pdf", "no_extension", "old.xls"])
def test_save_upload_file_unsupported_extension_raises_400(db_session, upload_env, bad_file):
    user = make_user(role="employee")
    with pytest.raises(HTTPException) as exc:
        upload_service.save_upload_file(
            db=db_session,
            file=make_upload_file(bad_file, b"data"),
            current_user=user,
        )
    assert exc.value.status_code == 400
    assert "Unsupported file format" in exc.value.detail


def test_save_upload_file_exceeds_max_size_raises_413_and_cleans_up(db_session, upload_env):
    user = make_user(role="employee")
    oversized = b"x" * (upload_env.max_size + 1)

    with pytest.raises(HTTPException) as exc:
        upload_service.save_upload_file(
            db=db_session,
            file=make_upload_file("big.csv", oversized),
            current_user=user,
        )
    assert exc.value.status_code == 413
    assert list(upload_env.upload_dir.glob("*")) == []
    assert db_session.query(UploadFile).count() == 0


def test_save_upload_file_empty_file_raises_400_and_cleans_up(db_session, upload_env):
    user = make_user(role="employee")
    with pytest.raises(HTTPException) as exc:
        upload_service.save_upload_file(
            db=db_session,
            file=make_upload_file("empty.csv", b""),
            current_user=user,
        )
    assert exc.value.status_code == 400
    assert "empty" in exc.value.detail.lower()
    assert list(upload_env.upload_dir.glob("*")) == []
    assert db_session.query(UploadFile).count() == 0


def test_save_upload_file_db_commit_failure_raises_500_and_cleans_up(
    db_session, upload_env, monkeypatch
):
    user = make_user(role="employee")
    monkeypatch.setattr(
        db_session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("DB write error"))
    )

    with pytest.raises(HTTPException) as exc:
        upload_service.save_upload_file(
            db=db_session,
            file=make_upload_file("ok.csv", b"a,b\n1,2\n"),
            current_user=user,
        )
    assert exc.value.status_code == 500
    assert list(upload_env.upload_dir.glob("*")) == []


def test_save_upload_file_path_traversal_filename_uses_uuid_storage(db_session, upload_env):
    user = make_user(role="employee")
    seed_user_in_db(db_session, user_id=user.id, role=user.role, branch_id=user.branch_id)
    record = upload_service.save_upload_file(
        db=db_session,
        file=make_upload_file("../../evil.csv", b"a,b\n1,2\n"),
        current_user=user,
    )
    assert record.original_filename == "../../evil.csv"
    assert Path(record.storage_path).parent == upload_env.upload_dir
    assert Path(record.storage_path).suffix == ".csv"


def _make_excel_file(filename: str, has_data: bool = True) -> FastAPIUploadFile:
    """Create an in-memory Excel file for testing."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    if has_data:
        ws.append(["col1", "col2"])
        ws.append([1, 2])
        ws.append([3, 4])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return FastAPIUploadFile(filename=filename, file=buf)


def test_save_upload_file_excel_success(db_session):
    user = make_user(role="manager", branch_id=uuid.uuid4())
    seed_user_in_db(db_session, user_id=user.id, role=user.role, branch_id=user.branch_id)
    upload = _make_excel_file("data.xlsx", has_data=True)
    record = upload_service.save_upload_file(
        db=db_session,
        file=upload,
        current_user=user,
        dataset_type="sales",
        branch_id=user.branch_id,
    )

    assert record.id is not None
    assert record.uploaded_by == user.id
    assert record.original_filename == "data.xlsx"
    assert record.file_type == "xlsx"
    assert record.file_size > 0
    assert record.status == "uploaded"
    assert record.dataset_type == "sales"
    assert Path(record.storage_path).exists()
    assert upload.file.closed


def test_save_upload_file_excel_empty_raises_400(db_session):
    user = make_user(role="employee")
    seed_user_in_db(db_session, user_id=user.id, role=user.role, branch_id=user.branch_id)
    upload = _make_excel_file("empty.xlsx", has_data=False)
    with pytest.raises(HTTPException) as exc:
        upload_service.save_upload_file(
            db=db_session,
            file=upload,
            current_user=user,
        )
    assert exc.value.status_code == 400
    assert "empty" in exc.value.detail.lower()
    assert db_session.query(UploadFile).count() == 0


def test_save_upload_file_excel_unreadable_raises_400(db_session):
    user = make_user(role="employee")
    seed_user_in_db(db_session, user_id=user.id, role=user.role, branch_id=user.branch_id)
    upload = FastAPIUploadFile(filename="corrupt.xlsx", file=io.BytesIO(b"not a real excel file"))
    with pytest.raises(HTTPException) as exc:
        upload_service.save_upload_file(
            db=db_session,
            file=upload,
            current_user=user,
        )
    assert exc.value.status_code == 400
    assert "Unable to read Excel file" in exc.value.detail
    assert db_session.query(UploadFile).count() == 0


# ---------------------------------------------------------------------------
# 3. list_upload_files Tests
# ---------------------------------------------------------------------------


def test_list_upload_files_roles_filters_and_pagination(db_session):
    branch_a = uuid.uuid4()
    branch_b = uuid.uuid4()
    admin = make_user(role="admin", branch_id=branch_a)
    mgr_a = make_user(role="manager", branch_id=branch_a)
    mgr_no_branch = make_user(role="manager", branch_id=None)
    emp_a1 = make_user(role="employee", branch_id=branch_a)
    emp_a2 = make_user(role="employee", branch_id=branch_a)

    now = datetime.now(timezone.utc)
    r1 = seed_upload(
        db_session,
        uploaded_by=emp_a1.id,
        branch_id=branch_a,
        status="uploaded",
        dataset_type="sales",
        uploaded_at=now - timedelta(minutes=2),
    )
    r2 = seed_upload(
        db_session,
        uploaded_by=emp_a2.id,
        branch_id=branch_a,
        status="processed",
        dataset_type="inventory",
        uploaded_at=now - timedelta(minutes=1),
    )
    r3 = seed_upload(
        db_session,
        uploaded_by=mgr_no_branch.id,
        branch_id=None,
        status="uploaded",
        dataset_type="sales",
        uploaded_at=now,
    )
    r4 = seed_upload(
        db_session,
        uploaded_by=uuid.uuid4(),
        branch_id=branch_b,
        status="uploaded",
        dataset_type="sales",
        uploaded_at=now + timedelta(minutes=1),
    )

    # Admin sees all 4 in descending order
    items, total = upload_service.list_upload_files(db_session, admin)
    assert total == 4
    assert [i.id for i in items] == [r4.id, r3.id, r2.id, r1.id]

    # Pagination
    paged, total = upload_service.list_upload_files(db_session, admin, skip=1, limit=2)
    assert total == 4
    assert [i.id for i in paged] == [r3.id, r2.id]

    # Manager with branch_a sees only branch_a records (r2, r1)
    mgr_items, mgr_total = upload_service.list_upload_files(db_session, mgr_a)
    assert mgr_total == 2
    assert {i.id for i in mgr_items} == {r1.id, r2.id}

    # Manager without branch sees only their own uploads (r3)
    nb_items, nb_total = upload_service.list_upload_files(db_session, mgr_no_branch)
    assert nb_total == 1
    assert nb_items[0].id == r3.id

    # Employee sees only their own uploads (r1)
    emp_items, emp_total = upload_service.list_upload_files(db_session, emp_a1)
    assert emp_total == 1
    assert emp_items[0].id == r1.id

    # Case-insensitive status + dataset_type filters
    filtered, f_total = upload_service.list_upload_files(
        db_session, admin, status_filter="UPLOADED", dataset_type="SALES"
    )
    assert f_total == 3
    assert {i.id for i in filtered} == {r1.id, r3.id, r4.id}


def test_list_upload_files_empty_result(db_session):
    emp = make_user(role="employee")
    items, total = upload_service.list_upload_files(db_session, emp)
    assert items == []
    assert total == 0


# ---------------------------------------------------------------------------
# 4. get_upload_file_by_id Tests
# ---------------------------------------------------------------------------


def test_get_upload_file_by_id_access_control(db_session):
    branch_a = uuid.uuid4()
    branch_b = uuid.uuid4()

    admin = make_user(role="admin", branch_id=branch_a)
    mgr_a = make_user(role="manager", branch_id=branch_a)
    mgr_no_branch = make_user(role="manager", branch_id=None)
    emp_a1 = make_user(role="employee", branch_id=branch_a)
    emp_a2 = make_user(role="employee", branch_id=branch_a)

    record = seed_upload(db_session, uploaded_by=emp_a1.id, branch_id=branch_a)
    other_branch_record = seed_upload(db_session, uploaded_by=uuid.uuid4(), branch_id=branch_b)
    own_no_branch_record = seed_upload(db_session, uploaded_by=mgr_no_branch.id, branch_id=None)

    # Positive access
    assert upload_service.get_upload_file_by_id(db_session, record.id, admin).id == record.id
    assert upload_service.get_upload_file_by_id(db_session, record.id, mgr_a).id == record.id
    assert upload_service.get_upload_file_by_id(db_session, record.id, emp_a1).id == record.id
    assert (
        upload_service.get_upload_file_by_id(db_session, own_no_branch_record.id, mgr_no_branch).id
        == own_no_branch_record.id
    )

    # Negative access: employee viewing another user's upload in same branch
    with pytest.raises(HTTPException) as exc:
        upload_service.get_upload_file_by_id(db_session, record.id, emp_a2)
    assert exc.value.status_code == 403

    # Negative access: manager viewing upload from different branch
    with pytest.raises(HTTPException) as exc:
        upload_service.get_upload_file_by_id(db_session, other_branch_record.id, mgr_a)
    assert exc.value.status_code == 403

    # Negative access: manager without branch viewing someone else's upload
    with pytest.raises(HTTPException) as exc:
        upload_service.get_upload_file_by_id(db_session, record.id, mgr_no_branch)
    assert exc.value.status_code == 403


def test_get_upload_file_by_id_not_found_raises_404(db_session):
    admin = make_user(role="admin")
    with pytest.raises(HTTPException) as exc:
        upload_service.get_upload_file_by_id(db_session, uuid.uuid4(), admin)
    assert exc.value.status_code == 404
    assert "Upload not found" in exc.value.detail