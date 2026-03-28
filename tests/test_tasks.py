"""Tests for task service — several tests deliberately expose the seeded bugs."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.task import Task  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services import task_service, user_service

# ---------------------------------------------------------------------------
# Test DB fixture
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///./test_taskflow.db"

engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_user(db, username="alice", email="alice@example.com"):
    return user_service.create_user(db, username, email, "password123")


# ---------------------------------------------------------------------------
# BUG-1: Pagination offset
# ---------------------------------------------------------------------------

def test_list_tasks_page1_returns_first_items(db):
    """Page 1 should return the first `limit` items, not skip them."""
    for i in range(5):
        task_service.create_task(db, title=f"Task {i}")

    page1 = task_service.list_tasks(db, page=1, limit=3)
    # BUG-1: currently returns [] because offset = 1*3 = 3, skipping items 0-2
    assert len(page1) == 3, f"Expected 3 tasks on page 1, got {len(page1)}"


# ---------------------------------------------------------------------------
# BUG-2: Priority validation
# ---------------------------------------------------------------------------

def test_create_task_rejects_invalid_priority(db):
    """Priority must be 1, 2, or 3 — not 0 or 99."""
    with pytest.raises(ValueError, match="priority"):
        task_service.create_task(db, title="Bad priority", priority=0)

    with pytest.raises(ValueError, match="priority"):
        task_service.create_task(db, title="Bad priority", priority=99)


# ---------------------------------------------------------------------------
# BUG-3: Assign to inactive user
# ---------------------------------------------------------------------------

def test_assign_task_rejects_inactive_user(db):
    """Assigning a task to a deactivated user should fail."""
    user = make_user(db)
    user_service.deactivate_user(db, user.id)

    task = task_service.create_task(db, title="My task")
    result = task_service.assign_task(db, task.id, user.id)
    # BUG-3: currently succeeds and assigns to inactive user
    assert result is None, "Should not assign task to inactive user"


# ---------------------------------------------------------------------------
# BUG-4: completed_at timestamp
# ---------------------------------------------------------------------------

def test_complete_task_sets_completed_at(db):
    """completed_at must be set on the very first completion call."""
    task = task_service.create_task(db, title="Finish me")
    completed = task_service.complete_task(db, task.id)

    # BUG-4: completed_at stays None because the branch checks `if task.is_completed`
    # which is False before completion
    assert completed.completed_at is not None, "completed_at must be set on completion"
    assert completed.is_completed is True


# ---------------------------------------------------------------------------
# BUG-6: Overdue tasks
# ---------------------------------------------------------------------------

def test_get_overdue_tasks_returns_past_due(db):
    """Overdue tasks have due_date in the past, not the future."""
    past = datetime.utcnow() - timedelta(days=1)
    future = datetime.utcnow() + timedelta(days=1)

    overdue_task = task_service.create_task(db, title="Late task", due_date=past)
    future_task = task_service.create_task(db, title="Future task", due_date=future)

    overdue = task_service.get_overdue_tasks(db)
    ids = [t.id for t in overdue]

    # BUG-6: currently returns future_task instead of overdue_task
    assert overdue_task.id in ids, "Past-due task must appear in overdue list"
    assert future_task.id not in ids, "Future task must NOT appear in overdue list"


# ---------------------------------------------------------------------------
# Happy path — these should pass even with bugs present
# ---------------------------------------------------------------------------

def test_create_and_get_task(db):
    task = task_service.create_task(db, title="Hello", priority=2)
    fetched = task_service.get_task(db, task.id)
    assert fetched.title == "Hello"
    assert fetched.priority == 2


def test_archive_task(db):
    task = task_service.create_task(db, title="Archive me")
    archived = task_service.archive_task(db, task.id)
    assert archived.is_archived is True


def test_list_tasks_excludes_archived_by_default(db):
    task_service.create_task(db, title="Active")
    archived = task_service.create_task(db, title="Archived")
    task_service.archive_task(db, archived.id)

    tasks = task_service.list_tasks(db, page=1, limit=10)
    titles = [t.title for t in tasks]
    assert "Archived" not in titles
