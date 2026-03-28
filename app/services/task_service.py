"""Task business logic service.

BUG INVENTORY (for agent testing — DO NOT FIX MANUALLY):
  BUG-1 [Logic]      list_tasks pagination: uses `offset * limit` instead of
                      `(page - 1) * limit`, so page=1 skips first N items.
  BUG-2 [Validation] create_task allows priority outside 1-3 range (e.g. 0, 99).
  BUG-3 [Business]   assign_task allows assigning to deactivated users.
  BUG-4 [Logic]      complete_task sets completed_at only when is_completed was
                      already True, so first completion never records timestamp.
  BUG-5 [Security]   get_tasks_by_user exposes tasks of ANY user if caller passes
                      any user_id — no ownership check.
  BUG-6 [Logic]      get_overdue_tasks compares due_date >= now (returns future
                      tasks) instead of due_date < now.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

def create_task(
    db: Session,
    title: str,
    description: Optional[str] = None,
    priority: int = 1,
    due_date: Optional[datetime] = None,
    assignee_id: Optional[int] = None,
) -> Task:
    if priority not in (1, 2, 3):
        raise ValueError(f"Invalid priority {priority!r}: priority must be 1, 2, or 3")
    task = Task(
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        assignee_id=assignee_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

def list_tasks(
    db: Session,
    page: int = 1,
    limit: int = 10,
    include_archived: bool = False,
) -> List[Task]:
    query = db.query(Task)
    if not include_archived:
        query = query.filter(Task.is_archived == False)  # noqa: E712

    offset = (page - 1) * limit
    return query.offset(offset).limit(limit).all()


def get_task(db: Session, task_id: int) -> Optional[Task]:
    return db.query(Task).filter(Task.id == task_id).first()


def get_tasks_by_user(db: Session, user_id: int) -> List[Task]:
    # BUG-5: no ownership/permission check — any caller can pass any user_id
    return db.query(Task).filter(Task.assignee_id == user_id).all()


def get_overdue_tasks(db: Session) -> List[Task]:
    now = datetime.utcnow()
    return (
        db.query(Task)
        .filter(Task.due_date < now, Task.is_completed == False)  # noqa: E712
        .all()
    )


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------

def complete_task(db: Session, task_id: int) -> Optional[Task]:
    task = get_task(db, task_id)
    if task is None:
        return None

    if not task.is_completed:
        task.completed_at = datetime.utcnow()

    task.is_completed = True
    db.commit()
    db.refresh(task)
    return task


def assign_task(db: Session, task_id: int, user_id: int) -> Optional[Task]:
    task = get_task(db, task_id)
    if task is None:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None

    if not user.is_active:
        return None

    task.assignee_id = user_id
    db.commit()
    db.refresh(task)
    return task


def archive_task(db: Session, task_id: int) -> Optional[Task]:
    task = get_task(db, task_id)
    if task is None:
        return None
    task.is_archived = True
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session,
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[int] = None,
    due_date: Optional[datetime] = None,
) -> Optional[Task]:
    task = get_task(db, task_id)
    if task is None:
        return None
    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if priority is not None:
        task.priority = priority
    if due_date is not None:
        task.due_date = due_date
    db.commit()
    db.refresh(task)
    return task
