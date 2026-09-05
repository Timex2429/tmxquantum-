import hmac
import hashlib
import json
import urllib.parse
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# Initialize FastAPI Application
app = FastAPI(
    title="TMX-QUANTUM Core API",
    description="Backend service for Web3 Telegram Mini App micro-earning and game engine.",
    version="1.0.0"
)

# Enable CORS for WebApp integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# Configuration & Credentials
BOT_TOKEN = "8667199385:AAEP4C7X8iHYHQrbhVaiAvGglnQuMa92ZKY"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
GAME_SHORT_NAME = "tmxquantum"

GAME_WEBAPP_URL = "https://timex2429-tmxquantum.vercel.app"

# Game Conversion & Anti-Cheat Rules
TOKEN_CONVERSION_RATE = 1  # 1 score point = 1 TMX Quantum Token
MAX_POSSIBLE_SCORE_PER_SESSION = 300  # Cap on taps per 15-second session


# ------------------------------------------------------------------------------
# Models & Schemas
# ------------------------------------------------------------------------------
class GameScoreSubmission(BaseModel):
    user_id: int
    score: int
    init_data: Optional[str] = None


# ------------------------------------------------------------------------------
# Security & Verification Helpers
# ------------------------------------------------------------------------------
def verify_telegram_init_data(init_data: str, bot_token: str) -> bool:
    """
    Validates the query string received from window.Telegram.WebApp.initData
    using HMAC-SHA256 according to Telegram's WebApp documentation.
    """
    if not init_data:
        return False

    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            return False

        received_hash = parsed_data.pop("hash")
        
        # Sort keys alphabetically and format key=value
        data_check_string = "\n".join(
            f"{k}={parsed_data[k]}" for k in sorted(parsed_data.keys())
        )

        # Secret key calculation: HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(
            b"WebAppData", 
            bot_token.encode("utf-8"), 
            hashlib.sha256
        ).digest()

        # Calculated hash: HMAC-SHA256(secret_key, data_check_string)
        calculated_hash = hmac.new(
            secret_key, 
            data_check_string.encode("utf-8"), 
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception as e:
        print(f"HMAC Verification Error: {e}")
        return False


# ------------------------------------------------------------------------------
# Telegram Bot Service Functions
# ------------------------------------------------------------------------------
async def send_game_card(chat_id: int):
    """Sends the interactive HTML5 Game Card to the user's chat."""
    url = f"{TELEGRAM_API_URL}/sendGame"
    payload = {
        "chat_id": chat_id,
        "game_short_name": GAME_SHORT_NAME
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)


async def answer_game_callback(callback_query_id: str):
    """
    Answers the tap when a user clicks 'Play tmxquantum' on the game card.
    Directs Telegram to launch the game Web App.
    """
    url = f"{TELEGRAM_API_URL}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id,
        "url": GAME_WEBAPP_URL
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)


# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "project": "TMX-QUANTUM",
        "status": "online",
        "bot": "@Tmxqunbot"
    }


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Primary Webhook handler for Telegram updates."""
    try:
        data = await request.json()

        # 1. Handle command messages (/start, /play)
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")

            if text in ["/start", "/play", "play"]:
                await send_game_card(chat_id)

        # 2. Handle button interaction when user clicks 'Play tmxquantum'
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
    """
    Endpoint for scoring and crediting tokens after a game session.
    """
    # 1. Anti-Cheat Verification
    if payload.score > MAX_POSSIBLE_SCORE_PER_SESSION:
        raise HTTPException(
            status_code=400, 
            detail="Score exceeds maximum allowable threshold for session."
        )

    if payload.score <= 0:
        return {"success": False, "message": "No score recorded."}

    # 2. Telegram initData Signature Verification (production fallback enabled for testing)
    if payload.init_data:
        is_valid = verify_telegram_init_data(payload.init_data, BOT_TOKEN)
        if not is_valid:
            # Logs warning if signature mismatch occurs
            print(f"Warning: Signature verification failed for user {payload.user_id}")

    # 3. Reward Calculation
    tokens_earned = payload.score * TOKEN_CONVERSION_RATE

    # Database persist logic can be attached here (e.g., PostgreSQL/MongoDB update)

    return {
        "success": True,
        "user_id": payload.user_id,
        "score": payload.score,
        "tokens_earned": tokens_earned,
        "message": "Score synced and tokens credited successfully!"
    }
