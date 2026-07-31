import hashlib
import hmac
import os
import urllib.parse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Retrieve Telegram Bot Token securely from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "")


class RewardClaimRequest(BaseModel):
    initData: str


def verify_telegram_webapp_data(init_data: str, bot_token: str) -> bool:
    """Validates Telegram WebApp initData against the bot token standard."""
    if not bot_token or not init_data:
        return False

    try:
        parsed_data = urllib.parse.parse_qs(init_data)
        if "hash" not in parsed_data:
            return False

        received_hash = parsed_data.pop("hash")[0]

        # Construct data check string (sorted keys with key=value format)
        items = sorted([(k, v[0]) for k, v in parsed_data.items()])
        data_check_string = "\n".join([f"{k}={v}" for k, v in items])

        # Calculate secret key using SHA256 HMAC of bot token
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
        ).digest()

        # Calculate hash of data_check_string using the secret key
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # Securely compare hashes
        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception:
        return False


# --- API Endpoints ---

@app.get("/")
async def read_root():
    return {
        "status": "online",
        "service": "TMX-QUANTUM API",
        "message": "FastAPI engine is running smoothly",
    }


@app.post("/api/claim-reward")
async def grant_reward(payload: RewardClaimRequest):
    # Validate Telegram WebApp initData
    if payload.initData:
        is_valid = verify_telegram_webapp_data(payload.initData, BOT_TOKEN)
        if not is_valid:
            raise HTTPException(
                status_code=400, detail="Invalid Telegram authentication data"
            )

    # Grant default reward amount
    return {
        "success": True,
        "message": "Reward claimed successfully",
        "reward_amount": 100,
    }
