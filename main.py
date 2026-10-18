from datetime import datetime, timedelta
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
    description="Backend engine for TMX Quantum Telegram Mini App",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# 2. MONGODB ATLAS CONNECTION
# ------------------------------------------------------------------
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://tmxquantum:tmxquantum123@cluster0.mongodb.net/tmxquantum?retryWrites=true&w=majority",
)
client = pymongo.MongoClient(MONGO_URI)
db = client["tmxquantum"]

BOT_TOKEN = os.getenv(
    "BOT_TOKEN", "8667199385:AAEP4C7X81HYHQrbhVaiAvGg1nQuMa92ZKY"
)
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ------------------------------------------------------------------
# 3. PYDANTIC REQUEST MODELS
# ------------------------------------------------------------------
class UserInitRequest(BaseModel):
  user_id: int
  username: Optional[str] = "Miner"
  referred_by: Optional[int] = None


class GameScoreSubmission(BaseModel):
  user_id: int
  score: int


class TaskClaimRequest(BaseModel):
  user_id: int
  task_id: str


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
  return {"message": "TMX Quantum API is active", "status": "online"}


@app.get("/api/health")
async def health_check():
  return {"status": "online", "project": "TMX-QUANTUM", "database": "connected"}


# ------------------------------------------------------------------
# 5. TELEGRAM WEBHOOK
# ------------------------------------------------------------------
@app.post("/webhook")
async def telegram_webhook(request: Request):
  try:
    update = await request.json()
  except Exception:
    raise HTTPException(status_code=400, detail="Invalid JSON payload")

  if "message" in update:
    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if text.startswith("/start") or text == "/play":
      welcome_text = (
          "⚡ *Welcome to TMX Quantum Mining!*\n\n"
          "Tap below to launch the Mini App, mine TMX tokens, complete"
          " tasks, and earn referral rewards!"
      )
      keyboard = {
          "inline_keyboard": [[{
              "text": "🚀 Launch TMX Quantum",
              "web_app": {"url": "https://timex2429-tmxquantum.vercel.app"},
          }]]
      }
      payload = {
          "chat_id": chat_id,
          "text": welcome_text,
          "parse_mode": "Markdown",
          "reply_markup": keyboard,
      }
      requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)

  return {"status": "ok"}


# ------------------------------------------------------------------
# 6. USER INIT & MONGODB REFERRAL SYSTEM
# ------------------------------------------------------------------
@app.post("/api/user/init")
async def initialize_user(data: UserInitRequest):
  try:
    user = db.users.find_one({"user_id": data.user_id})

    if not user:
      welcome_bonus = 0

      # Credit Referrer (+500 TMX) if valid referral link used
      if data.referred_by and data.referred_by != data.user_id:
        db.users.update_one(
            {"user_id": data.referred_by},
            {"$inc": {"balance": 500, "referrals_count": 1}},
            upsert=True,
        )
        welcome_bonus = 200  # Give new user +200 bonus

      new_user = {
          "user_id": data.user_id,
          "username": data.username or "Miner",
          "balance": welcome_bonus,
          "referred_by": data.referred_by,
          "referrals_count": 0,
          "completed_tasks": [],
          "last_daily_claim": None,
          "daily_streak": 0,
          "last_spin_time": None,
          "wallet_address": None,
          "created_at": datetime.utcnow(),
      }
      db.users.insert_one(new_user)
      user = new_user

    return {
        "status": "success",
        "user_id": user["user_id"],
        "username": user.get("username", "Miner"),
        "balance": user.get("balance", 0),
        "referrals_count": user.get("referrals_count", 0),
        "completed_tasks": user.get("completed_tasks", []),
        "daily_streak": user.get("daily_streak", 0),
        "wallet_address": user.get("wallet_address", None),
    }
  except Exception as e:
    return {"status": "error", "message": str(e)}


# ------------------------------------------------------------------
# 7. GAME SCORE & BALANCE MANAGEMENT
# ------------------------------------------------------------------
@app.post("/api/game/submit-score")
async def submit_score(data: GameScoreSubmission):
  if data.score < 0:
    raise HTTPException(status_code=400, detail="Invalid score format")

  user = db.users.find_one_and_update(
      {"user_id": data.user_id},
      {"$inc": {"balance": data.score}},
      upsert=True,
      return_document=pymongo.ReturnDocument.AFTER,
  )

  return {
      "status": "success",
      "user_id": data.user_id,
      "score_added": data.score,
      "total_balance": user.get("balance", 0),
  }


@app.get("/api/user/{user_id}/data")
async def get_user_data(user_id: int):
  user = db.users.find_one({"user_id": user_id})
  if not user:
    return {"status": "not_found", "balance": 0, "referrals_count": 0}

  return {
      "status": "success",
      "user_id": user_id,
      "username": user.get("username", "Miner"),
      "balance": user.get("balance", 0),
      "referrals_count": user.get("referrals_count", 0),
      "completed_tasks": user.get("completed_tasks", []),
      "daily_streak": user.get("daily_streak", 0),
      "wallet_address": user.get("wallet_address"),
  }


# ------------------------------------------------------------------
# 8. SOCIAL MEDIA & DAILY TASKS SYSTEM
# ------------------------------------------------------------------
TASKS = {
    "telegram_channel": {
        "reward": 1000,
        "title": "Join Telegram Channel",
    },
    "twitter_follow": {"reward": 1000, "title": "Follow us on X"},
    "youtube_sub": {"reward": 1500, "title": "Subscribe on YouTube"},
}


@app.post("/api/tasks/claim")
async def claim_task(data: TaskClaimRequest):
  if data.task_id not in TASKS:
    raise HTTPException(status_code=404, detail="Task not found")

  user = db.users.find_one({"user_id": data.user_id})
  if not user:
    raise HTTPException(status_code=404, detail="User not found")

  completed_tasks = user.get("completed_tasks", [])
  if data.task_id in completed_tasks:
    return {"status": "already_claimed", "balance": user.get("balance", 0)}

  reward = TASKS[data.task_id]["reward"]

  updated_user = db.users.find_one_and_update(
      {"user_id": data.user_id},
      {
          "$inc": {"balance": reward},
          "$push": {"completed_tasks": data.task_id},
      },
      return_document=pymongo.ReturnDocument.AFTER,
  )

  return {
      "status": "claimed",
      "reward": reward,
      "total_balance": updated_user.get("balance", 0),
      "completed_tasks": updated_user.get("completed_tasks", []),
  }


# ------------------------------------------------------------------
# 9. DAILY LOGIN STREAK REWARDS
# ------------------------------------------------------------------
@app.post("/api/daily/claim")
async def claim_daily_reward(data: TaskClaimRequest):  # Reusing TaskClaimRequest
  user = db.users.find_one({"user_id": data.user_id})
  if not user:
    raise HTTPException(status_code=404, detail="User not found")

  now = datetime.utcnow()
  last_claim = user.get("last_daily_claim")
  streak = user.get("daily_streak", 0)

  if last_claim:
    time_diff = now - last_claim
    if time_diff < timedelta(hours=24):
      return {
          "status": "cooldown",
          "message": "Daily reward already claimed today",
      }
    elif time_diff > timedelta(hours=48):
      streak = 0  # Reset streak if missed a day

  streak += 1
  reward = 500 * streak  # Incremental daily reward

  updated_user = db.users.find_one_and_update(
      {"user_id": data.user_id},
      {
          "$inc": {"balance": reward},
          "$set": {"last_daily_claim": now, "daily_streak": streak},
      },
      return_document=pymongo.ReturnDocument.AFTER,
  )

  return {
      "status": "success",
      "reward": reward,
      "streak": streak,
      "total_balance": updated_user.get("balance", 0),
  }


# ------------------------------------------------------------------
# 10. DAILY LUCKY SPIN WHEEL
# ------------------------------------------------------------------
@app.post("/api/spin/claim")
async def spin_wheel(data: SpinRequest):
  user = db.users.find_one({"user_id": data.user_id})
  if not user:
    raise HTTPException(status_code=404, detail="User not found")

  now = datetime.utcnow()
  last_spin = user.get("last_spin_time")

  if last_spin and (now - last_spin) < timedelta(hours=12):
    return {
        "status": "cooldown",
        "message": "Spin available every 12 hours",
    }

  # Spin probabilities / rewards
  spin_rewards = [100, 250, 500, 1000, 2500, 5000]
  won_reward = random.choice(spin_rewards)

  updated_user = db.users.find_one_and_update(
      {"user_id": data.user_id},
      {"$inc": {"balance": won_reward}, "$set": {"last_spin_time": now}},
      return_document=pymongo.ReturnDocument.AFTER,
  )

  return {
      "status": "success",
      "reward_won": won_reward,
      "total_balance": updated_user.get("balance", 0),
  }


# ------------------------------------------------------------------
# 11. TON WALLET CONNECT SAVE
# ------------------------------------------------------------------
@app.post("/api/wallet/save")
async def save_wallet(data: WalletSaveRequest):
  db.users.update_one(
      {"user_id": data.user_id},
      {"$set": {"wallet_address": data.wallet_address}},
      upsert=True,
  )
  return {"status": "success", "wallet_address": data.wallet_address}
