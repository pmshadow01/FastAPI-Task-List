from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime, date, timezone
import itertools
import os

app = FastAPI(title="Tasks API Demo", version="1.0")

# Simple API key for security, ask me for it :)
API_KEY = os.getenv("API_KEY", "supersecret123")
def require_key(x_api_key: str = Header(..., alias="x-api-key")):
    if x_api_key != API_KEY:
        raise HTTPException(401, "Invalid or missing API key")

# Set types
Priority = Literal["low", "medium", "high"]
Status = Literal["todo", "doing", "done"]

class TaskIn(BaseModel):
    # Incoming payload for create/replace
    title: str = Field(..., min_length=4, max_length=100)
    description: Optional[str] = Field(None, max_length=100)
    priority: Priority = "medium"
    status: Status = "todo"
    due_date: Optional[date] = None

    @field_validator("due_date")
    @classmethod
    def due_not_past(cls, v: Optional[date]) -> Optional[date]:
        if v and v < date.today():
            raise ValueError("due_date cannot be in the past")
        return v

class TaskUpdate(BaseModel):
    # Partial update; only provided fields will be applied
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    priority: Optional[Priority] = None
    status: Optional[Status] = None
    due_date: Optional[date] = None

    @field_validator("due_date")
    @classmethod
    def due_not_past(cls, v: Optional[date]) -> Optional[date]:
        if v and v < date.today():
            raise ValueError("due_date cannot be in the past")
        return v
    
class Task(TaskIn):
    id: int
    created_at: datetime
    updated_at: datetime

# Naive in-memory database, resets on process restart.
DB: dict[int, Task] = {}
_id_counter = itertools.count(1) # increase id count with itertools

@app.get("/")
def root():
    # Landing message, OpenAPI docs at /docs.
    return {"message": "Welcome to my Tasks API! See /docs for usage."}

@app.post("/tasks/", response_model=Task, tags=["tasks"], dependencies=[Depends(require_key)], status_code=201)
def create_task(payload: TaskIn):
    # Create and store a new task, server sets id/timestamps
    now = datetime.now(timezone.utc)
    tid = next(_id_counter)
    task = Task(id=tid, created_at=now, updated_at=now, **payload.model_dump())
    DB[tid] = task
    return task

@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"], dependencies=[Depends(require_key)])
def get_task(task_id: int):
    # 404 if the task doesn't exist
    task = DB.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task

@app.put("/tasks/{task_id}", response_model=Task, tags=["tasks"], dependencies=[Depends(require_key)])
def replace_task(task_id: int, payload: TaskIn):
    # Full replace functionality, keep original created_at
    if task_id not in DB:
        raise HTTPException(404, "Task not found")
    now = datetime.now(timezone.utc)
    task = Task(id=task_id, created_at=DB[task_id].created_at, updated_at=now, **payload.model_dump())
    DB[task_id] = task
    return task

@app.patch("/tasks/{task_id}", response_model=Task, tags=["tasks"], dependencies=[Depends(require_key)])
def update_task(task_id: int, payload: TaskUpdate):
    # Partial update, only apply to fields the client sent
    if task_id not in DB:
        raise HTTPException(404, "Task not found")
    existing = DB[task_id]
    data = existing.model_dump()
    data.update(payload.model_dump(exclude_unset=True))
    data["updated_at"] = datetime.now(timezone.utc)
    DB[task_id] = Task(**data)
    return DB[task_id]

@app.delete("/tasks/{task_id}", status_code=204, tags=["tasks"], dependencies=[Depends(require_key)])
def delete_task(task_id: int):
    # 204 No Content on successful deletion
    if task_id not in DB:
        raise HTTPException(404, "Task not found")
    del DB[task_id]
    return

@app.get("/tasks", response_model=list[Task], tags=["tasks"], dependencies=[Depends(require_key)])
def list_tasks_simple():
    # Return all tasks (unsorted) from the in-memory store
    return list(DB.values())