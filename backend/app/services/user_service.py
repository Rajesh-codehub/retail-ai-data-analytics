from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.schemas.auth import UserCreate


from uuid import UUID

from app.schemas.auth import UserUpdate


def get_user_by_id(db: Session, user_id: UUID):
    return db.query(User).filter(User.id == user_id).first()


def get_users(db: Session, skip: int = 0, limit: int = 20):
    return (
        db.query(User)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_user(
    db: Session,
    user: User,
    user_data: UserUpdate,
):
    update_data = user_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return user


def deactivate_user(db: Session, user: User):
    user.is_active = False

    db.commit()
    db.refresh(user)

    return user

def create_user(db: Session, user_data: UserCreate):
    existing_user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_user:
        raise ValueError("Email already registered")

    user = User(
        employee_id=user_data.employee_id,
        name=user_data.name,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role=user_data.role,
        branch_id=user_data.branch_id,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user