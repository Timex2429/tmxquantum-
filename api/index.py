import os
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient

app = FastAPI(
    title="TMX Quantum API",
    description="Backend engine for TMX Quantum Telegram Mini App",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8667199385:AAEP4C7X8iHYHQrbhVaiAvGglnQuMa92ZKY")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_db_collection():
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise HTTPException(status_code=500, detail="MONGO_URI environment variable not configured")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client["TMX-QUANTUM"]
    return db["users"]


class GameScoreSubmission(BaseModel):
    user_id: int
    score: int


@app.get("/")
@app.get("/api/health")
async def health_check():
    try:
        users_collection = get_db_collection()
        users_collection.command("ping")
        return {"status": "online", "project": "TMX-QUANTUM", "database": "MongoDB Atlas Connected"}
    except Exception as e:
        return {"status": "online", "project": "TMX-QUANTUM", "database_error": str(e)}


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

        if text in ["/start", "/play"]:
            welcome_text = (
                "⚡ *Welcome to TMX Quantum Mining!*\n\n"
                "Tap below to launch the Mini App, mine TMX tokens, and complete rewarded tasks."
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🚀 Launch TMX Quantum",
                            "web_app": {"url": "https://tmxquantum-ten.vercel.app"}
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
    if data.score < 0:
        raise HTTPException(status_code=400, detail="Invalid score format")

    users_collection = get_db_collection()
    result = users_collection.find_one_and_update(
        {"user_id": data.user_id},
        {"$inc": {"balance": data.score}},
        upsert=True,
        return_document=True
    )

    new_balance = result.get("balance", data.score) if result else data.score

    return {
        "status": "success",
        "user_id": data.user_id,
        "score_added": data.score,
        "total_balance": new_balance
    }


@app.get("/api/user/{user_id}/balance")
async def get_balance(user_id: int):
    users_collection = get_db_collection()
    user = users_collection.find_one({"user_id": user_id})
    balance = user.get("balance", 0) if user else 0
    return {"user_id": user_id, "balance": balance}
