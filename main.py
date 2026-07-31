from typing import List
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

# Import your database models, schemas, and dependencies here:
# from .database import get_db
# from .models import User, Task
# from .schemas import TaskResponse, TaskVerifyRequest
# from .auth import get_current_user

app = FastAPI()

# --- PASTE YOUR MIDDLEWARE HERE ---
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    response = await call_next(request)
    return response
# -----------------------------------

@app.get("/")
def read_root():
    return {"message": "Hello World"}



@app.get("/")
def read_root():
    return {"message": "Hello World"}


@app.get("/api/tasks", response_model=List[TaskResponse])
def list_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tasks = db.query(Task).filter(Task.is_active == True).all()
    
    # Create a set of task IDs the current user has already completed
    user_completed_ids = {t.id for t in current_user.completed_tasks}

    # Map database Task models to the TaskResponse Pydantic schema
    response = []
    for t in tasks:
        response.append(
            TaskResponse(
                id=t.id,
                title=t.title,
                reward=t.reward,
                task_type=t.task_type,
                url=t.url,
                is_completed=(t.id in user_completed_ids)
            )
        )
    return response


@app.post("/api/tasks/claim")
def verify_and_claim_task(
    payload: TaskVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Claims reward for standard tasks like X follow, Telegram join, or posting."""
    task = db.query(Task).filter(Task.id == payload.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task in current_user.completed_tasks:
        raise HTTPException(status_code=400, detail="Task already completed")

    # Add task to completed list and credit user
    current_user.completed_tasks.append(task)
    current_user.tmx_balance += task.reward
    db.commit()
    db.refresh(current_user)

    return {
        "status": "success",
        "task_id": task.id,
        "reward_credited": task.reward,
        "new_balance": current_user.tmx_balance
    }
