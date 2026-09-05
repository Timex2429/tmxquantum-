import hmac
import hashlib
import json
import urllib.parse
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

app = FastAPI(
    title="TMX-QUANTUM Core API",
    description="Backend service for Web3 Telegram Mini App micro-earning and game engine.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOT_TOKEN = "8667199385:AAEP4C7X8iHYHQrbhVaiAvGglnQuMa92ZKY"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
GAME_SHORT_NAME = "tmxquantum"
GAME_WEBAPP_URL = "https://timex2429-tmxquantum.vercel.app"

TOKEN_CONVERSION_RATE = 1
MAX_POSSIBLE_SCORE_PER_SESSION = 300


class GameScoreSubmission(BaseModel):
    user_id: int
    score: int
    init_data: Optional[str] = None


def verify_telegram_init_data(init_data: str, bot_token: str) -> bool:
    if not init_data:
        return False
    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            return False
        received_hash = parsed_data.pop("hash")
        data_check_string = "\n".join(
            f"{k}={parsed_data[k]}" for k in sorted(parsed_data.keys())
        )
        secret_key = hmac.new(
            b"WebAppData", 
            bot_token.encode("utf-8"), 
            hashlib.sha256
        ).digest()
        calculated_hash = hmac.new(
            secret_key, 
            data_check_string.encode("utf-8"), 
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception as e:
        print(f"HMAC Verification Error: {e}")
        return False


async def send_game_card(chat_id: int):
    url = f"{TELEGRAM_API_URL}/sendGame"
    payload = {
        "chat_id": chat_id,
        "game_short_name": GAME_SHORT_NAME
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)


async def answer_game_callback(callback_query_id: str):
    url = f"{TELEGRAM_API_URL}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id,
        "url": GAME_WEBAPP_URL
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)


@app.get("/")
async def root():
    return {
        "project": "TMX-QUANTUM",
        "status": "online",
        "bot": "@Tmxqunbot"
    }


@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()

        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")

            if text in ["/start", "/play", "play"]:
                await send_game_card(chat_id)

        if "callback_query" in data:
            callback_id = data["callback_query"]["id"]
            if data["callback_query"].get("game_short_name") == GAME_SHORT_NAME:
                await answer_game_callback(callback_id)

        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook Exception: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/game/submit-score")
async def submit_game_score(payload: GameScoreSubmission):
    if payload.score > MAX_POSSIBLE_SCORE_PER_SESSION:
        raise HTTPException(
            status_code=400, 
            detail="Score exceeds maximum allowable threshold for session."
        )

    if payload.score <= 0:
        return {"success": False, "message": "No score recorded."}

    if payload.init_data:
        is_valid = verify_telegram_init_data(payload.init_data, BOT_TOKEN)
        if not is_valid:
            print(f"Warning: Signature verification failed for user {payload.user_id}")

    tokens_earned = payload.score * TOKEN_CONVERSION_RATE

    return {
        "success": True,
        "user_id": payload.user_id,
        "score": payload.score,
        "tokens_earned": tokens_earned,
        "message": "Score synced and tokens credited successfully!"
    }
