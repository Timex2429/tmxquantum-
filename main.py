import hmac
import hashlib
import json
from urllib.parse import parse_qsl, unquote
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="TMX-QUANTUM API")

# --- 1. ENABLE CORS (Fixes "Failed to fetch") ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any frontend domain
    allow_credentials=True,
    allow_methods=["*"],  # Allows POST, GET, OPTIONS, etc.
    allow_headers=["*"],
)

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

class RewardClaimRequest(BaseModel):
    initData: str = ""

def verify_telegram_data(init_data: str) -> bool:
    """Validates Telegram WebApp initData against Bot Token signature."""
    if not BOT_TOKEN:
        # Fallback for testing environment if TOKEN is missing
        return True
    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        hash_check = parsed_data.pop("hash", None)
        if not hash_check:
            return False

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        return hmac.compare_digest(calculated_hash, hash_check)
    except Exception:
        return False

# --- API Endpoints ---

@app.get("/")
async def read_root():
    return {
        "status": "online",
        "service": "TMX-QUANTUM API",
        "message": "FastAPI engine is running smoothly"
    }

@app.post("/api/grant-reward")
async def grant_reward(payload: RewardClaimRequest):
    # Allow bypass during development if initData is empty, or validate signature
    if payload.initData:
        is_valid = verify_telegram_data(payload.initData)
        if not is_valid:
            raise HTTPException(status_code=403, detail="Invalid Telegram signature authentication")

    # Grant default reward amount
    return {
        "success": True,
        "message": "Reward claimed successfully!",
        "reward_amount": 100
    }
