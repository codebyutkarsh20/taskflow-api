# TaskFlow API

Simple task management REST API built with FastAPI + SQLAlchemy + SQLite.

## Setup

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload      # http://localhost:8000
```

## Run Tests

```bash
pytest tests/ -v
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /tasks/ | Create task |
| GET | /tasks/ | List tasks (paginated) |
| GET | /tasks/{id} | Get task |
| PATCH | /tasks/{id} | Update task |
| POST | /tasks/{id}/complete | Complete task |
| POST | /tasks/{id}/assign/{user_id} | Assign task |
| POST | /tasks/{id}/archive | Archive task |
| GET | /tasks/overdue | Get overdue tasks |
| GET | /tasks/user/{user_id} | Get tasks by user |
| POST | /users/ | Create user |
| GET | /users/{id} | Get user |
| POST | /users/{id}/deactivate | Deactivate user |
