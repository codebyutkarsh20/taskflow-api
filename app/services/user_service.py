"""User management service."""
import hashlib
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User


def _hash_password(password: str) -> str:
    # Simple SHA-256 hash (not production-safe, intentional for simplicity)
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(db: Session, username: str, email: str, password: str) -> User:
    if db.query(User).filter(User.username == username).first():
        raise ValueError(f"Username '{username}' already taken")
    if db.query(User).filter(User.email == email).first():
        raise ValueError(f"Email '{email}' already registered")

    user = User(
        username=username,
        email=email,
        hashed_password=_hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def deactivate_user(db: Session, user_id: int) -> Optional[User]:
    user = get_user(db, user_id)
    if user is None:
        return None
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, username)
    if user is None:
        return None
    if user.hashed_password != _hash_password(password):
        return None
    if not user.is_active:
        return None
    return user
