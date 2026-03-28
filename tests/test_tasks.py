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


# ---------------------------------------------------------------------------
# Additional tests for all 5 bugs
# ---------------------------------------------------------------------------

def test_pagination_offset_page1_is_zero(db):
    """Page 1 with limit 10 should use offset 0, returning first items."""
    for i in range(15):
        task_service.create_task(db, title=f"Task {i}")

    page1 = task_service.list_tasks(db, page=1, limit=10)
    page2 = task_service.list_tasks(db, page=2, limit=10)

    assert len(page1) == 10, f"Expected 10 tasks on page 1, got {len(page1)}"
    assert len(page2) == 5, f"Expected 5 tasks on page 2, got {len(page2)}"
    # Ensure no overlap between pages
    ids1 = {t.id for t in page1}
    ids2 = {t.id for t in page2}
    assert ids1.isdisjoint(ids2), "Page 1 and page 2 should not share tasks"


def test_create_task_valid_priorities(db):
    """Priorities 1, 2, and 3 should all be accepted."""
    for p in (1, 2, 3):
        task = task_service.create_task(db, title=f"Task p={p}", priority=p)
        assert task.priority == p


def test_create_task_invalid_priority_zero(db):
    """Priority 0 must raise ValueError."""
    with pytest.raises(ValueError, match="priority"):
        task_service.create_task(db, title="Bad", priority=0)


def test_create_task_invalid_priority_four(db):
    """Priority 4 must raise ValueError."""
    with pytest.raises(ValueError, match="priority"):
        task_service.create_task(db, title="Bad", priority=4)


def test_create_task_invalid_priority_negative(db):
    """Negative priority must raise ValueError."""
    with pytest.raises(ValueError, match="priority"):
        task_service.create_task(db, title="Bad", priority=-1)


def test_assign_task_active_user_succeeds(db):
    """Assigning a task to an active user should succeed."""
    user = make_user(db)
    task = task_service.create_task(db, title="Assign me")
    result = task_service.assign_task(db, task.id, user.id)
    assert result is not None
    assert result.assignee_id == user.id


def test_assign_task_inactive_user_returns_none(db):
    """Assigning a task to an inactive user must return None."""
    user = make_user(db)
    user_service.deactivate_user(db, user.id)
    task = task_service.create_task(db, title="Should not assign")
    result = task_service.assign_task(db, task.id, user.id)
    assert result is None, "Expected None when assigning to inactive user"


def test_complete_task_already_completed_is_idempotent(db):
    """Completing an already-completed task should return the task without error."""
    task = task_service.create_task(db, title="Complete twice")
    first = task_service.complete_task(db, task.id)
    assert first.is_completed is True
    assert first.completed_at is not None
    first_completed_at = first.completed_at

    second = task_service.complete_task(db, task.id)
    assert second.is_completed is True
    # completed_at should not change on second call
    assert second.completed_at == first_completed_at


def test_complete_task_sets_completed_at_on_first_call(db):
    """completed_at must be populated on the very first complete_task call."""
    task = task_service.create_task(db, title="First completion")
    assert task.is_completed is False

    completed = task_service.complete_task(db, task.id)
    assert completed.is_completed is True
    assert completed.completed_at is not None


def test_get_overdue_tasks_excludes_future_tasks(db):
    """Tasks with due_date in the future must NOT appear in overdue list."""
    future = datetime.utcnow() + timedelta(days=5)
    task_service.create_task(db, title="Future task", due_date=future)

    overdue = task_service.get_overdue_tasks(db)
    titles = [t.title for t in overdue]
    assert "Future task" not in titles


def test_get_overdue_tasks_includes_past_due_tasks(db):
    """Tasks with due_date in the past and not completed must appear in overdue list."""
    past = datetime.utcnow() - timedelta(days=2)
    task_service.create_task(db, title="Overdue task", due_date=past)

    overdue = task_service.get_overdue_tasks(db)
    titles = [t.title for t in overdue]
    assert "Overdue task" in titles


def test_get_overdue_tasks_excludes_completed_tasks(db):
    """Completed tasks should not appear in overdue list even if past due."""
    past = datetime.utcnow() - timedelta(days=1)
    task = task_service.create_task(db, title="Completed overdue", due_date=past)
    task_service.complete_task(db, task.id)

    overdue = task_service.get_overdue_tasks(db)
    ids = [t.id for t in overdue]
    assert task.id not in ids, "Completed tasks must not appear in overdue list"
