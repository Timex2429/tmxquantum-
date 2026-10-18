import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import requests

app = FastAPI(
    title="TMX Quantum API",
    description="Backend engine for TMX Quantum Telegram Mini App",
    version="1.0.0"
)

# Enable CORS for Telegram Web App frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8667199385:AAEP4C7X8iHYHQrbhVaiAvGglnQuMa92ZKY")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# In-memory storage for user balances (Replace with Database in production)
user_balances = {}


class GameScoreSubmission(BaseModel):
    user_id: int
    score: int
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
      "message": "Welcome to TMX Quantum API",
      "status": "active",
      "error": "index.html path not resolved",
  }



@app.get("/api/health")
async def health_check():
  return {"status": "online", "project": "TMX-QUANTUM"}
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

        if text == "/start" or text == "/play":
            welcome_text = (
                "⚡ *Welcome to TMX Quantum Mining!*\n\n"
                "Tap below to launch the Mini App, mine TMX tokens, and complete rewarded tasks."
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🚀 Launch TMX Quantum",
                            "web_app": {"url": "https://timex2429-tmxquantum.vercel.app"}
                        }
                    ]
                ]
            }
            
            payload = {
                "chat_id": chat_id,
                "text": welcome_text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }
            
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)

    return {"status": "ok"}h
class GameScoreSubmission(BaseModel):
  user_id: int
  score: int


class UserInitRequest(BaseModel):
  user_id: int
  referred_by: Optional[int] = None


@app.post("/api/user/init")
async def initialize_user(data: UserInitRequest):
  try:
    existing_user = db.users.find_one({"user_id": data.user_id})

    if not existing_user:
      welcome_bonus = 0

      # Credit referrer (+500) if friend joined via referral link
      if data.referred_by and data.referred_by != data.user_id:
        db.users.update_one(
            {"user_id": data.referred_by},
            {"$inc": {"balance": 500, "referrals_count": 1}},
            upsert=True,
        )
        welcome_bonus = 200

      new_user = {
          "user_id": data.user_id,
          "balance": welcome_bonus,
          "referred_by": data.referred_by,
          "referrals_count": 0,
          "wallet_address": None,
      }
      db.users.insert_one(new_user)
      return {
          "status": "created",
          "balance": welcome_bonus,
          "referrals_count": 0,
      }

    return {
        "status": "exists",
        "balance": existing_user.get("balance", 0),
        "referrals_count": existing_user.get("referrals_count", 0),
    }
  except Exception as e:
    return {"status": "error", "message": str(e)}


@app.post("/api/game/submit-score")
async def submit_score(data: GameScoreSubmission):
  if data.score < 0:
    raise HTTPException(status_code=400, detail="Invalid score format")

  # Atomically update balance directly in MongoDB Atlas
  user = db.users.find_one_and_update(
      {"user_id": data.user_id},
      {"$inc": {"balance": data.score}},
      upsert=True,
      return_document=True,
  )

  return {
      "status": "success",
      "user_id": data.user_id,
      "score_added": data.score,
      "total_balance": user.get("balance", 0) if user else data.score,
  }


@app.get("/api/user/{user_id}/balance")
async def get_balance(user_id: int):
  user = db.users.find_one({"user_id": user_id})
  balance = user.get("balance", 0) if user else 0
  return {"user_id": user_id, "balance": balance}
