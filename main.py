import os
import json
import hashlib
import hmac
from urllib.parse import parse_qsl

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ==========================================
# Configuration (secrets come from env vars)
# ==========================================
# Set TELEGRAM_BOT_TOKEN in your Vercel project (Settings -> Environment Variables)
# and locally in a .env file. Never hardcode tokens in source.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

app = FastAPI()

# Enable CORS so your frontend and backend communicate smoothly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def serve_frontend():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    return {"status": "Online", "message": "Backend is running!"}


# ==========================================
# Telegram Authentication & Validation Setup
# ==========================================
def verify_telegram_init_data(init_data: str, bot_token: str) -> bool:
    """Validates the initData string sent from the Telegram WebApp SDK."""
    if not bot_token:
        return False
    try:
        parsed_data = dict(parse_qsl(init_data, strict_parsing=True))
        if "hash" not in parsed_data:
            return False
        received_hash = parsed_data.pop("hash")

        # Sort remaining keys alphabetically and construct the data check string
        sorted_pairs = sorted(parsed_data.items())
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_pairs)

        # Generate HMAC-SHA256 signature using "WebAppData" as the key
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256,
        ).digest()

        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Securely compare hashes to prevent timing attacks
        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception:
        return False


# ==========================================
# Models & Endpoints
# ==========================================
class ClaimRequest(BaseModel):
    init_data: str
    reward_amount: float


@app.post("/api/tmx/claim")
async def claim_tmx_rewards(payload: ClaimRequest):
    # 1. Security Check: Verify request comes legitimately from Telegram
    if not verify_telegram_init_data(payload.init_data, TELEGRAM_BOT_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid Telegram signature.",
        )

    # 2. Extract user details safely from the validated init_data
    parsed_data = dict(parse_qsl(payload.init_data))
    user_json = parsed_data.get("user")

    if not user_json:
        raise HTTPException(
            status_code=400,
            detail="User data missing from session.",
        )

    user_data = json.loads(user_json)
    telegram_user_id = user_data.get("id")
    username = user_data.get("username", "Unknown")

    # 3. Process your database update here (e.g., add tokens for telegram_user_id)

    return {
        "success": True,
        "message": f"Successfully credited {payload.reward_amount} TMX to user @{username}!",
    }


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if chat_id and text and TELEGRAM_BOT_TOKEN:
        reply_text = f"Received your message: '{text}'"
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={"chat_id": chat_id, "text": reply_text})

    return {"status": "ok"}
