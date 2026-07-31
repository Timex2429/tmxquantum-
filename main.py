import os
import hmac
import hashlib
import json
from urllib.parse import parse_qs, unquote
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

# ---------------------------------------------------------
# CONFIGURATION & DATABASE SETUP
# ---------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tmx_quantum.db")

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------------------------------------------------------
# DATABASE MODELS
# ---------------------------------------------------------
# Junction table for User <-> Task (Completed Tasks)
user_tasks = Table(
    'user_completed_tasks',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('task_id', String, ForeignKey('tasks.id'))
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True) # Telegram User ID
    first_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    tmx_balance = Column(Float, default=0.0)
    referral_code = Column(String, unique=True, index=True)
    referred_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    completed_tasks = relationship("Task", secondary=user_tasks, backref="completed_by")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True) # e.g. "join_telegram_channel"
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    category = Column(String, default="social") # social, referral, daily, partner
    reward = Column(Float, default=100.0) # TMX tokens granted
    link = Column(String, nullable=True)
    icon_type = Column(String, default="default") # twitter, telegram, register, invite


Base.metadata.create_all(bind=engine)

# Dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------
# FASTAPI APP & CORS
# ---------------------------------------------------------
app = FastAPI(title="TMX-QUANTUM API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Tighten in production if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# TELEGRAM AUTHENTICATION HELPER
# ---------------------------------------------------------
def verify_telegram_data(init_data: str) -> dict:
    """Validates Telegram WebApp initData against the bot token."""
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData header")

    try:
        parsed_data = parse_qs(init_data)
        if "hash" not in parsed_data:
            raise HTTPException(status_code=400, detail="Invalid initData format")

        hash_val = parsed_data.pop("hash")[0]

        # Sort keys in lexicographical order
        data_check_arr = []
        for key in sorted(parsed_data.keys()):
            val = parsed_data[key][0]
            data_check_arr.append(f"{key}={val}")

        data_check_string = "\n".join(data_check_arr)

        # HMAC SHA256 Verification
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if calculated_hash != hash_val:
            raise HTTPException(status_code=403, detail="Unauthorized request source")

        user_raw = parsed_data.get("user", [None])[0]
        if not user_raw:
            raise HTTPException(status_code=400, detail="User payload missing")

        return json.loads(unquote(user_raw))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"Authentication error: {str(e)}")


def get_current_user(x_telegram_init_data: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    user_data = verify_telegram_data(x_telegram_init_data)
    user_id = user_data["id"]

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(
            id=user_id,
            first_name=user_data.get("first_name", ""),
            username=user_data.get("username", ""),
            referral_code=f"tmx_{user_id}"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user

# ---------------------------------------------------------
# PYDANTIC SCHEMAS
# ---------------------------------------------------------
class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str
    reward: float
    link: Optional[str]
    icon_type: str
    is_completed: bool

class TaskVerifyRequest(BaseModel):
    task_id: str

# ---------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------

@app.on_event("startup")
def populate_default_tasks():
    """Initializes standard social and growth tasks into DB on startup."""
    db = SessionLocal()
    default_tasks = [
        {
            "id": "follow_x",
            "title": "Follow TMX-QUANTUM on X",
            "description": "Follow our official X handle for updates.",
            "reward": 250.0,
            "category": "social",
            "link": "https://x.com/TMX_Quantum",
            "icon_type": "twitter"
        },
        {
            "id": "join_tg_channel",
            "title": "Join Announcement Channel",
            "description": "Stay tuned with real-time news in our Telegram channel.",
            "reward": 200.0,
            "category": "social",
            "link": "https://t.me/TMXQuantumChannel",
            "icon_type": "telegram"
        },
        {
            "id": "join_tg_group",
            "title": "Join Global Community Group",
            "description": "Interact with other TMX miners in the main group.",
            "reward": 200.0,
            "category": "social",
            "link": "https://t.me/TMXQuantumGroup",
            "icon_type": "telegram"
        },
        {
            "id": "post_channel_social",
            "title": "Post About Us on Social Media",
            "description": "Share TMX-QUANTUM on X or Facebook.",
            "reward": 500.0,
            "category": "social",
            "link": "https://x.com/intent/tweet?text=Mining%20TMX%20Tokens%20on%20Telegram!",
            "icon_type": "share"
        },
        {
            "id": "invite_3_friends",
            "title": "Invite 3 Friends",
            "description": "Share your referral link with at least 3 active users.",
            "reward": 1000.0,
            "category": "referral",
            "link": None,
            "icon_type": "invite"
        },
    ]

    for t_data in default_tasks:
        existing = db.query(Task).filter(Task.id == t_data["id"]).first()
        if not existing:
            task = Task(**t_data)
            db.add(task)
    db.commit()
    db.close()


@app.get("/api/user/me")
def get_user_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "first_name": current_user.first_name,
        "username": current_user.username,
        "tmx_balance": current_user.tmx_balance,
        "referral_code": current_user.referral_code
    }
@app.post("/api/mine/claim")
def claim_mined_reward(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    reward_amount = 50.0  # TMX granted per claim
    current_user.tmx_balance += reward_amount
    db.commit()
    db.refresh(current_user)

    return {
        "status": "success",
        "added": reward_amount,
        "new_balance": current_user.tmx_balance
    }
    return {
    "status": "success",
    "added": reward_amount,
    "new_balance": current_user.tmx_balance
}
return { ... }  # <--- This second return is unreachable code.

@app.get("/api/tasks", response_model=List[TaskResponse])
def list_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
  tasks = db.query(Task).filter(Task.is_active == True).all()  # Optional enhancement
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
        raise HTTPException(status_code=44, detail="Task not found")

    if task in current_user.completed_tasks:
        raise HTTPException(status_code=400, detail="Task already completed")

    # Add task to completed list and credit user
    current_user.completed_tasks.append(task)
    current_user.tmx_balance += task.reward
    db.commit()

    return {
        "status": "success",
        "task_id": task.id,
        "reward_credited": task.reward,
        "new_balance": current_user.tmx_balance
    }
