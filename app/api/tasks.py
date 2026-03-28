"""Task API endpoints."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: int = 1
    due_date: Optional[datetime] = None
    assignee_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    due_date: Optional[datetime] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    priority: int
    is_completed: bool
    is_archived: bool
    due_date: Optional[datetime]
    created_at: datetime
    completed_at: Optional[datetime]
    assignee_id: Optional[int]

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=TaskResponse, status_code=200)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    """Create a new task. Returns 200 (should be 201)."""
    return task_service.create_task(
        db,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_date=payload.due_date,
        assignee_id=payload.assignee_id,
    )


@router.get("/", response_model=List[TaskResponse])
def list_tasks(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
):
    """List tasks with pagination."""
    return task_service.list_tasks(db, page=page, limit=limit, include_archived=include_archived)


@router.get("/overdue", response_model=List[TaskResponse])
def get_overdue_tasks(db: Session = Depends(get_db)):
    """Get all overdue incomplete tasks."""
    return task_service.get_overdue_tasks(db)


@router.get("/user/{user_id}", response_model=List[TaskResponse])
def get_user_tasks(user_id: int, db: Session = Depends(get_db)):
    """Get all tasks assigned to a user."""
    return task_service.get_tasks_by_user(db, user_id)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = task_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = task_service.update_task(db, task_id, **payload.model_dump(exclude_none=True))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(task_id: int, db: Session = Depends(get_db)):
    """Mark a task as complete."""
    task = task_service.complete_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/assign/{user_id}", response_model=TaskResponse)
def assign_task(task_id: int, user_id: int, db: Session = Depends(get_db)):
    """Assign a task to a user."""
    task = task_service.assign_task(db, task_id, user_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task or user not found")
    return task


@router.post("/{task_id}/archive", response_model=TaskResponse)
def archive_task(task_id: int, db: Session = Depends(get_db)):
    task = task_service.archive_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
