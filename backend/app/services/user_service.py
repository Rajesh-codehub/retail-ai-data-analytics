from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.schemas.auth import UserCreate
from sqlalchemy.exc import IntegrityError

from uuid import UUID

from app.schemas.auth import UserUpdate

import logging

# Initialize logger for this module
logger = logging.getLogger(__name__)


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


logger = logging.getLogger(__name__)

def create_user(db: Session, user_data: UserCreate):
    logger.info(f"Attempting to create user - Email: {user_data.email}, Employee ID: {user_data.employee_id}")

    # Check for existing email
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        logger.warning(f"User creation failed: Email '{user_data.email}' is already registered.")
        raise ValueError("Email already registered")

    # Check for existing employee_id
    existing_emp = db.query(User).filter(User.employee_id == user_data.employee_id).first()
    if existing_emp:
        logger.warning(f"User creation failed: Employee ID '{user_data.employee_id}' is already registered.")
        raise ValueError("Employee ID already registered")

    try:
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
        
        logger.info(f"Successfully created user with ID: {user.id}")
        return user

    except IntegrityError as e:  # <-- Fixed: changed from InterruptedError to IntegrityError
        db.rollback()
        logger.error(f"Database IntegrityError during user creation for {user_data.email}: {e.orig}")
        raise



# def create_user(db: Session, user_data: UserCreate):
#     existing_user = (
#         db.query(User)
#         .filter(User.email == user_data.email)
#         .first()
#     )

#     if existing_user:
#         raise ValueError("Email already registered")


#     user = User(
#         employee_id=user_data.employee_id,
#         name=user_data.name,
#         email=user_data.email,
#         password_hash=hash_password(user_data.password),
#         role=user_data.role,
#         branch_id=user_data.branch_id,
#     )

#     db.add(user)
#     db.commit()
#     db.refresh(user)

#     return user