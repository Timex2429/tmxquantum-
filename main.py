from datetime import datetime, timedelta, timezone
import os
import random
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pymongo
import requests

# ------------------------------------------------------------------
# 1. APP & CORS SETUP
# ------------------------------------------------------------------
app = FastAPI(
    title="TMX Quantum API",
    description="Backend engine for TMX-QUANTUM Telegram Mini App & Web3 Mining",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# 2. MONGODB ATLAS & BOT CONFIGURATION
# ------------------------------------------------------------------
MONGO_URI = (
    os.getenv("MONGO_URL")
    or os.getenv("MONGO_URI")
    or os.getenv("MONGODB_URI")
    or "mongodb+srv://horaltmitchell_db_user:Arizabalaga25@tmx-quantum.mqltymh.mongodb.net/tmxquantum?retryWrites=true&w=majority"
)
DB_NAME = os.getenv("MONGODB_DB_NAME", "tmxquantum")

client: Optional[pymongo.MongoClient] = None
db = None

try:
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    client.admin.command("ping")
    db.users.create_index([("user_id", pymongo.ASCENDING)], unique=True)
    db.users.create_index([("balance", pymongo.DESCENDING)])
    print(f"✅ Successfully connected to MongoDB Atlas database '{DB_NAME}'!")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8667199385:AAEP4C7X81HYHQrbhVaiAvGg1nQuMa92ZKY")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://timex2429-tmxquantum.vercel.app")


def get_db():
    if db is None or client is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_user_id(raw_id: Optional[int | str], tg_user: Optional[dict] = None) -> int:
    candidate = raw_id if raw_id not in (None, "", "guest_local") else (tg_user or {}).get("id")
    if candidate is None:
        raise HTTPException(status_code=400, detail="Valid user_id is required")
    try:
        uid = int(candidate)
        if uid <= 0:
            raise ValueError("user_id must be positive")
        return uid
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user_id format")


def resolve_username(raw_username: Optional[str], uid: int, tg_user: Optional[dict] = None) -> str:
    if raw_username and str(raw_username).strip() and str(raw_username) != "You (Local)":
        return str(raw_username).strip()
    if tg_user:
        if tg_user.get("username"):
            return f"@{tg_user['username']}"
        full_name = " ".join(
            part for part in [tg_user.get("first_name"), tg_user.get("last_name")] if part
        ).strip()
        if full_name:
            return full_name
    return f"Miner_{uid}"


def ensure_user_doc(database, uid: int, username: str, referred_by: Optional[int] = None) -> dict:
    now = utc_now()
    user = database.users.find_one({"user_id": uid})
    if not user:
        welcome_bonus = 0
        if referred_by and referred_by != uid:
            referrer = database.users.find_one({"user_id": referred_by})
            if referrer:
                database.users.update_one(
                    {"user_id": referred_by},
                    {
                        "$inc": {"balance": 500, "referrals_count": 1},
                        "$push": {"referred_users": uid},
                    },
                )
                welcome_bonus = 200

        user = {
            "user_id": uid,
            "username": username,
            "balance": welcome_bonus,
            "referred_by": referred_by,
            "referrals_count": 0,
            "referred_users": [],
            "completed_tasks": [],
            "last_daily_claim": None,
            "last_bonus_date": None,
            "daily_streak": 0,
            "last_spin_time": None,
            "wallet_address": None,
            "created_at": now,
            "updated_at": now,
        }
        database.users.insert_one(user)
    elif username and user.get("username") != username and not (
        user.get("username") and not str(user.get("username")).startswith("Miner_")
    ):
        database.users.update_one(
            {"user_id": uid},
            {"$set": {"username": username, "updated_at": now}},
        )
        user["username"] = username
    return user


def build_leaderboard(database, limit: int = 20) -> list[dict]:
    safe_limit = max(1, min(int(limit), 100))
    cursor = (
        database.users.find({}, {"_id": 0, "user_id": 1, "username": 1, "balance": 1, "completed_tasks": 1})
        .sort("balance", pymongo.DESCENDING)
        .limit(safe_limit)
    )
    items = []
    for doc in cursor:
        uid = doc.get("user_id")
        items.append({
            "user_id": uid,
            "username": doc.get("username") or f"Miner_{uid}",
            "balance": int(doc.get("balance", 0) or 0),
            "tasksCount": len(doc.get("completed_tasks") or []),
        })
    return items


# ------------------------------------------------------------------
# 3. PYDANTIC REQUEST MODELS
# ------------------------------------------------------------------
class UserInitRequest(BaseModel):
    user_id: int
    username: Optional[str] = "Miner"
    referred_by: Optional[int] = None


class StateSyncRequest(BaseModel):
    user_id: Optional[int | str] = None
    username: Optional[str] = None
    user: Optional[dict] = None
    initData: Optional[str] = None


class MineClaimRequest(BaseModel):
    user_id: Optional[int | str] = None
    username: Optional[str] = None
    user: Optional[dict] = None
    sessionPoints: Optional[int] = None
    score: Optional[int] = None
    multiplier: Optional[int] = 1
    earned: Optional[int] = None


class GameScoreSubmission(BaseModel):
    user_id: int
    score: int


class TaskClaimRequest(BaseModel):
    user_id: Optional[int | str] = None
    username: Optional[str] = None
    user: Optional[dict] = None
    task_id: Optional[str] = None
    taskId: Optional[str] = None
    reward: Optional[int] = None


class DailyClaimRequest(BaseModel):
    user_id: Optional[int | str] = None
    username: Optional[str] = None
    user: Optional[dict] = None
    reward: Optional[int] = None
    date: Optional[str] = None


class SpinRequest(BaseModel):
    user_id: int


class WalletSaveRequest(BaseModel):
    user_id: int
    wallet_address: str


# ------------------------------------------------------------------
# 4. STATIC FRONTEND & HEALTH ENDPOINTS
# ------------------------------------------------------------------
@app.get("/")
async def serve_frontend():
    possible_paths = [
        os.path.join(os.getcwd(), "index.html"),
        os.path.join(os.path.dirname(__file__), "..", "index.html"),
        os.path.join(os.path.dirname(__file__), "index.html"),
        "index.html",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path)
    return {
        "message": "TMX-QUANTUM API is active and running",
        "status": "online",
    }


@app.api_route("/api/health", methods=["GET", "POST"])
async def health_check():
    db_status = "disconnected"
    try:
        if client is not None:
            client.admin.command("ping")
            db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "ok": db_status == "connected",
        "status": "online",
        "project": "TMX-QUANTUM",
        "database": db_status,
        "timestamp": utc_now().isoformat(),
    }


# ------------------------------------------------------------------
# 5. TELEGRAM WEBHOOK
# ------------------------------------------------------------------
@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if isinstance(update, dict) and "message" in update:
        message = update["message"]
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        if chat_id and (text.startswith("/start") or text == "/play"):
            welcome_text = (
                "⚡ *Welcome to TMX-QUANTUM Mining!*\n\n"
                "Tap below to launch the Mini App, mine TMX tokens, complete"
                " missions, spin the wheel, and earn referral rewards!"
            )
            keyboard = {
                "inline_keyboard": [[{
                    "text": "🚀 Launch TMX-QUANTUM",
                    "web_app": {"url": MINI_APP_URL},
                }]]
            }
            payload = {
                "chat_id": chat_id,
                "text": welcome_text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            }
            try:
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=5)
            except Exception as exc:
                print(f"⚠️ Failed to send Telegram message: {exc}")

    return {"status": "ok"}


# ------------------------------------------------------------------
# 6. USER INIT, STATE SYNC & REFERRAL SYSTEM
# ------------------------------------------------------------------
@app.post("/api/user/init")
async def initialize_user(data: UserInitRequest):
    database = get_db()
    try:
        uname = resolve_username(data.username, data.user_id)
        user = ensure_user_doc(database, data.user_id, uname, referred_by=data.referred_by)
        return {
            "status": "success",
            "ok": True,
            "user_id": user["user_id"],
            "username": user.get("username", uname),
            "balance": int(user.get("balance", 0) or 0),
            "referrals_count": int(user.get("referrals_count", 0) or 0),
            "completed_tasks": user.get("completed_tasks", []),
            "daily_streak": int(user.get("daily_streak", 0) or 0),
            "wallet_address": user.get("wallet_address", None),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/state")
async def sync_state(data: StateSyncRequest):
    database = get_db()
    try:
        uid = resolve_user_id(data.user_id, data.user)
        uname = resolve_username(data.username, uid, data.user)
        user = ensure_user_doc(database, uid, uname)
        return {
            "ok": True,
            "status": "success",
            "user_id": uid,
            "username": user.get("username", uname),
            "balance": int(user.get("balance", 0) or 0),
            "completedTasks": user.get("completed_tasks", []),
            "lastBonusDate": user.get("last_bonus_date"),
            "referrals_count": int(user.get("referrals_count", 0) or 0),
            "daily_streak": int(user.get("daily_streak", 0) or 0),
            "wallet_address": user.get("wallet_address"),
            "leaderboard": build_leaderboard(database, 25),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# 7. GAME SCORE, MINING CLAIM & BALANCE MANAGEMENT
# ------------------------------------------------------------------
@app.post("/api/game/submit-score")
async def submit_score(data: GameScoreSubmission):
    database = get_db()
    if data.score < 0:
        raise HTTPException(status_code=400, detail="Invalid score format")

    try:
        user = database.users.find_one_and_update(
            {"user_id": data.user_id},
            {
                "$inc": {"balance": int(data.score)},
                "$setOnInsert": {
                    "username": f"Miner_{data.user_id}",
                    "completed_tasks": [],
                    "created_at": utc_now(),
                },
                "$set": {"updated_at": utc_now()},
            },
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER,
        )
        return {
            "status": "success",
            "ok": True,
            "user_id": data.user_id,
            "score_added": int(data.score),
            "total_balance": int(user.get("balance", 0) or 0),
            "balance": int(user.get("balance", 0) or 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mine/claim")
async def claim_mining_session(data: MineClaimRequest):
    database = get_db()
    try:
        uid = resolve_user_id(data.user_id, data.user)
        uname = resolve_username(data.username, uid, data.user)
        ensure_user_doc(database, uid, uname)

        mult = 2 if data.multiplier == 2 else 1
        points = max(0, int(data.sessionPoints or 0))
        raw_earned = data.earned if data.earned is not None else (data.score if data.score is not None else points * mult)
        earned = int(raw_earned or 0)

        if earned < 0 or earned > 10000:
            raise HTTPException(status_code=400, detail="Invalid earned amount")

        updated = database.users.find_one_and_update(
            {"user_id": uid},
            {
                "$inc": {"balance": earned},
                "$set": {"username": uname, "updated_at": utc_now()},
            },
            return_document=pymongo.ReturnDocument.AFTER,
        )

        return {
            "ok": True,
            "status": "success",
            "earned": earned,
            "balance": int(updated.get("balance", 0) or 0),
            "total_balance": int(updated.get("balance", 0) or 0),
            "leaderboard": build_leaderboard(database, 25),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/user/{user_id}/data")
async def get_user_data(user_id: int):
    database = get_db()
    try:
        user = database.users.find_one({"user_id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "status": "success",
            "user_id": user_id,
            "username": user.get("username", "Miner"),
            "balance": int(user.get("balance", 0) or 0),
            "referrals_count": int(user.get("referrals_count", 0) or 0),
            "completed_tasks": user.get("completed_tasks", []),
            "daily_streak": int(user.get("daily_streak", 0) or 0),
            "wallet_address": user.get("wallet_address"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# 8. TASKS & VERIFICATION SYSTEM
# ------------------------------------------------------------------
TASKS = {
    "bot_tmxqunbot": {
        "reward": 25,
        "title": "Launch Official Bot (@Tmxqunbot)",
        "link": "https://t.me/Tmxqunbot",
    },
    "x_timex2429": {
        "reward": 20,
        "title": "Follow on X (@timex2429)",
        "link": "https://x.com/timex2429",
    },
    "ig_tmxquantum245": {
        "reward": 20,
        "title": "Follow on Instagram (@tmxquantum245)",
        "link": "https://instagram.com/tmxquantum245",
    },
    "first_mine": {
        "reward": 15,
        "title": "Complete First 15s Mining Session",
        "link": None,
    },
    "share_app": {
        "reward": 30,
        "title": "Share TMX-QUANTUM with a Friend",
        "link": None,
    },
    "telegram_channel": {
        "reward": 1000,
        "title": "Join Official Telegram Channel",
        "link": "https://t.me/tmxquantum",
    },
    "twitter_follow": {
        "reward": 1000,
        "title": "Follow us on X (Twitter)",
        "link": "https://x.com/timex2429",
    },
    "instagram_follow": {
        "reward": 1000,
        "title": "Follow us on Instagram",
        "link": "https://instagram.com/tmxquantum245",
    },
    "youtube_sub": {
        "reward": 1500,
        "title": "Subscribe on YouTube",
        "link": "https://youtube.com/@tmxquantum",
    },
    "telegram_chat": {
        "reward": 800,
        "title": "Join TMX-Quantum Official Chat",
        "link": "https://t.me/+LW4DJIurXOE0ZGU0",
    },
}


@app.get("/api/tasks/{user_id}")
async def get_tasks(user_id: int):
    database = get_db()
    user = database.users.find_one({"user_id": user_id})
    completed_tasks = user.get("completed_tasks", []) if user else []

    tasks_list = []
    for task_id, info in TASKS.items():
        tasks_list.append({
            "task_id": task_id,
            "title": info["title"],
            "reward": info["reward"],
            "link": info["link"],
            "completed": task_id in completed_tasks,
        })

    return {"status": "success", "tasks": tasks_list}


async def _process_task_claim(database, uid: int, uname: str, task_id: Optional[str], fallback_reward: Optional[int]):
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")

    user = ensure_user_doc(database, uid, uname)
    completed_tasks = user.get("completed_tasks", [])

    if task_id in completed_tasks:
        return {
            "ok": True,
            "status": "already_claimed",
            "message": "Task already completed",
            "balance": int(user.get("balance", 0) or 0),
            "total_balance": int(user.get("balance", 0) or 0),
            "completedTasks": completed_tasks,
            "completed_tasks": completed_tasks,
        }

    if task_id in TASKS:
        reward = int(TASKS[task_id]["reward"])
    elif fallback_reward is not None:
        reward = max(0, min(int(fallback_reward), 2000))
    else:
        raise HTTPException(status_code=404, detail="Task not found")

    updated_user = database.users.find_one_and_update(
        {"user_id": uid},
        {
            "$inc": {"balance": reward},
            "$addToSet": {"completed_tasks": task_id},
            "$set": {"username": uname, "updated_at": utc_now()},
        },
        return_document=pymongo.ReturnDocument.AFTER,
    )

    updated_tasks = updated_user.get("completed_tasks", [])
    return {
        "ok": True,
        "status": "success",
        "reward": reward,
        "balance": int(updated_user.get("balance", 0) or 0),
        "total_balance": int(updated_user.get("balance", 0) or 0),
        "completedTasks": updated_tasks,
        "completed_tasks": updated_tasks,
    }


@app.post("/api/tasks/claim")
async def claim_task(data: TaskClaimRequest):
    database = get_db()
    try:
        uid = resolve_user_id(data.user_id, data.user)
        uname = resolve_username(data.username, uid, data.user)
        tid = data.task_id or data.taskId
        return await _process_task_claim(database, uid, uname, tid, data.reward)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/verify")
async def verify_task(data: TaskClaimRequest):
    database = get_db()
    try:
        uid = resolve_user_id(data.user_id, data.user)
        uname = resolve_username(data.username, uid, data.user)
        tid = data.taskId or data.task_id
        return await _process_task_claim(database, uid, uname, tid, data.reward)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# 9. DAILY LOGIN STREAK & BONUS REWARDS
# ------------------------------------------------------------------
async def _process_daily_bonus(database, uid: int, uname: str, requested_reward: Optional[int] = None, date_str: Optional[str] = None):
    user = ensure_user_doc(database, uid, uname)
    now = utc_now()
    today_key = date_str or now.strftime("%Y-%m-%d")

    if user.get("last_bonus_date") == today_key:
        bal = int(user.get("balance", 0) or 0)
        return {
            "ok": True,
            "status": "cooldown",
            "message": "Daily reward already claimed today.",
            "balance": bal,
            "total_balance": bal,
            "lastBonusDate": today_key,
        }

    last_claim = user.get("last_daily_claim")
    if isinstance(last_claim, datetime) and last_claim.tzinfo is None:
        last_claim = last_claim.replace(tzinfo=timezone.utc)

    streak = int(user.get("daily_streak", 0) or 0)
    if last_claim:
        time_diff = now - last_claim
        if time_diff < timedelta(hours=24):
            bal = int(user.get("balance", 0) or 0)
            return {
                "ok": True,
                "status": "cooldown",
                "message": "Daily reward already claimed today. Try again later.",
                "balance": bal,
                "total_balance": bal,
                "lastBonusDate": today_key,
            }
        elif time_diff > timedelta(hours=48):
            streak = 0

    streak += 1
    reward = int(requested_reward) if requested_reward and requested_reward > 0 else 20

    updated_user = database.users.find_one_and_update(
        {"user_id": uid},
        {
            "$inc": {"balance": reward},
            "$set": {
                "last_daily_claim": now,
                "last_bonus_date": today_key,
                "daily_streak": streak,
                "username": uname,
                "updated_at": now,
            },
        },
        return_document=pymongo.ReturnDocument.AFTER,
    )

    bal = int(updated_user.get("balance", 0) or 0)
    return {
        "ok": True,
        "status": "success",
        "reward": reward,
        "streak": streak,
        "balance": bal,
        "total_balance": bal,
        "lastBonusDate": today_key,
    }


@app.post("/api/daily/claim")
async def claim_daily_reward(data: DailyClaimRequest):
    database = get_db()
    try:
        uid = resolve_user_id(data.user_id, data.user)
        uname = resolve_username(data.username, uid, data.user)
        return await _process_daily_bonus(database, uid, uname, data.reward, data.date)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bonus/claim")
async def claim_bonus(data: DailyClaimRequest):
    database = get_db()
    try:
        uid = resolve_user_id(data.user_id, data.user)
        uname = resolve_username(data.username, uid, data.user)
        return await _process_daily_bonus(database, uid, uname, data.reward, data.date)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# 10. DAILY LUCKY SPIN WHEEL
# ------------------------------------------------------------------
@app.post("/api/spin/claim")
async def spin_wheel(data: SpinRequest):
    database = get_db()
    user = database.users.find_one({"user_id": data.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = utc_now()
    last_spin = user.get("last_spin_time")
    if isinstance(last_spin, datetime) and last_spin.tzinfo is None:
        last_spin = last_spin.replace(tzinfo=timezone.utc)

    if last_spin and (now - last_spin) < timedelta(hours=12):
        return {
            "status": "cooldown",
            "message": "Spin available every 12 hours. Please check back later.",
        }

    spin_rewards = [100, 250, 500, 1000, 2500, 5000]
    won_reward = random.choice(spin_rewards)

    updated_user = database.users.find_one_and_update(
        {"user_id": data.user_id},
        {
            "$inc": {"balance": won_reward},
            "$set": {"last_spin_time": now, "updated_at": now},
        },
        return_document=pymongo.ReturnDocument.AFTER,
    )

    return {
        "status": "success",
        "reward_won": won_reward,
        "total_balance": int(updated_user.get("balance", 0) or 0),
        "balance": int(updated_user.get("balance", 0) or 0),
    }


# ------------------------------------------------------------------
# 11. TON WALLET CONNECT SAVE
# ------------------------------------------------------------------
@app.post("/api/wallet/save")
async def save_wallet(data: WalletSaveRequest):
    database = get_db()
    user = database.users.find_one_and_update(
        {"user_id": data.user_id},
        {"$set": {"wallet_address": data.wallet_address, "updated_at": utc_now()}},
        return_document=pymongo.ReturnDocument.AFTER,
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "status": "success",
        "wallet_address": data.wallet_address,
        "message": "TON Wallet saved successfully",
    }


# ------------------------------------------------------------------
# 12. LEADERBOARD SYSTEM
# ------------------------------------------------------------------
@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 20):
    database = get_db()
    try:
        items = build_leaderboard(database, limit)
        return {"status": "success", "ok": True, "leaderboard": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
