import os
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

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

    return {"status": "ok"}


@app.post("/api/game/submit-score")
async def submit_score(data: GameScoreSubmission):
    user_id = data.user_id
    points_earned = data.score

    if points_earned < 0:
        raise HTTPException(status_code=400, detail="Invalid score format")

    current_balance = user_balances.get(user_id, 0)
    new_balance = current_balance + points_earned
    user_balances[user_id] = new_balance

    return {
        "status": "success",
        "user_id": user_id,
        "score_added": points_earned,
        "total_balance": new_balance
    }


@app.get("/api/user/{user_id}/balance")
async def get_balance(user_id: int):
    balance = user_balances.get(user_id, 0)
    return {"user_id": user_id, "balance": balance}
