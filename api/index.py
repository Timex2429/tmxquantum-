import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
import requests

app = FastAPI(
    title="TMX Quantum API",
    description="Serverless API engine for TMX-QUANTUM Telegram Mini App",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://www.tmxquantum.site")
DB_NAME = os.getenv("MONGODB_DB_NAME", "tmxquantum")

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    global _client
    mongo_uri = (
        os.getenv("MONGO_URI")
        or os.getenv("MONGO_URL")
        or os.getenv("MONGODB_URI")
    )
    if not mongo_uri:
        raise HTTPException(
            status_code=500,
            detail="MONGO_URI environment variable not configured",
        )
    if _client is None:
        _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    return _client


def get_db_collection():
    client = get_client()
    db = client[DB_NAME]
    return db["users"]


class GameScoreSubmission(BaseModel):
    user_id: int
    score: int


@app.get("/")
@app.api_route("/api/health", methods=["GET", "POST"])
async def health_check():
    try:
        client = get_client()
        client.admin.command("ping")
        return {
            "ok": True,
            "status": "online",
            "project": "TMX-QUANTUM",
            "database": "MongoDB Atlas Connected",
        }
    except HTTPException as exc:
        return {
            "ok": False,
            "status": "online",
            "project": "TMX-QUANTUM",
            "database_error": exc.detail,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "online",
            "project": "TMX-QUANTUM",
            "database_error": str(exc),
        }


@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if isinstance(update, dict) and "message" in update and BOT_TOKEN:
        message = update["message"]
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = message.get("text", "")

        if chat_id and (text.startswith("/start") or text == "/play"):
            welcome_text = (
                "⚡ *Welcome to TMX-QUANTUM!*\n\n"
                "Launch the Mini App below to run 15-second rounds, complete"
                " ecosystem quests, claim daily streaks, and link your TON wallet."
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🚀 Launch TMX-QUANTUM",
                            "web_app": {"url": MINI_APP_URL},
                        }
                    ]
                ]
            }

            payload = {
                "chat_id": chat_id,
                "text": welcome_text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            }

            try:
                requests.post(
                    f"{TELEGRAM_API_URL}/sendMessage",
                    json=payload,
                    timeout=5,
                )
            except Exception as exc:
                print(f"Failed to send Telegram webhook message: {exc}")

    return {"status": "ok"}


@app.post("/api/game/submit-score")
async def submit_score(data: GameScoreSubmission):
    if data.score < 0 or data.score > 10000:
        raise HTTPException(status_code=400, detail="Invalid score value")

    users_collection = get_db_collection()
    result = users_collection.find_one_and_update(
        {"user_id": data.user_id},
        {
            "$inc": {"balance": int(data.score)},
            "$setOnInsert": {"username": f"Operator_{data.user_id}", "completed_tasks": []},
        },
        upsert=True,
        return_document=True,
    )

    new_balance = int(result.get("balance", data.score) or 0) if result else int(data.score)

    return {
        "ok": True,
        "status": "success",
        "user_id": data.user_id,
        "score_added": int(data.score),
        "total_balance": new_balance,
        "balance": new_balance,
    }


@app.get("/api/user/{user_id}/balance")
async def get_balance(user_id: int):
    users_collection = get_db_collection()
    user = users_collection.find_one({"user_id": user_id})
    balance = int(user.get("balance", 0) or 0) if user else 0
    return {"user_id": user_id, "balance": balance}
