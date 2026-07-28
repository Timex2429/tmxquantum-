import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# 1. Retrieve Telegram Bot Token safely from Vercel Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# 2. Initialize FastAPI Application
app = FastAPI(
    title="TMX Quantum API",
    description="Backend API for TMX-QUANTUM Telegram Mini App",
    version="1.0.0"
)

# 3. Configure CORS Middleware (Allows your Vercel frontend to communicate with this backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Data Models ---
class RewardClaimRequest(BaseModel):
    initData: str  # Raw initData string sent from Telegram WebApp SDK


# --- Helper Functions ---
def verify_telegram_data(init_data: str) -> bool:
    """
    Validates Telegram initData hash using HMAC-SHA256 and TELEGRAM_TOKEN.
    """
    if not TELEGRAM_TOKEN:
        print("Warning: TELEGRAM_TOKEN environment variable is missing.")
        return False

    try:
        parsed_data = dict(parse_qsl(init_data))
        if "hash" not in parsed_data:
            return False

        received_hash = parsed_data.pop("hash")
        
        # Sort key-value pairs alphabetically
        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(parsed_data.items())
        )

        # Generate HMAC-SHA256 secret key from token
        secret_key = hmac.new(
            b"WebAppData", TELEGRAM_TOKEN.encode("utf-8"), hashlib.sha256
        ).digest()

        # Calculate expected hash
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception as e:
        print(f"Validation error: {e}")
        return False


# --- API Endpoints ---

@app.get("/")
async def read_root():
    """Health check endpoint to verify backend status."""
    return {
        "status": "online",
        "service": "TMX Quantum API",
        "message": "FastAPI engine is running smoothly!"
    }


@app.post("/api/grant-reward")
async def grant_reward(payload: RewardClaimRequest):
    """
    Validates Telegram user authentication and processes Adsgram ad rewards.
    """
    if not payload.initData:
        raise HTTPException(status_code=400, detail="Missing initData string in request body.")

    # Validate signature against Telegram Bot Token
    is_valid = verify_telegram_data(payload.initData)
    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid Telegram authentication payload.")

    # Extract user information from validated initData
    parsed_data = dict(parse_qsl(payload.initData))
    user_info = json.loads(parsed_data.get("user", "{}"))
    telegram_id = user_info.get("id")

    # TODO: Add your database/token minting logic here (e.g., update user balance)

    return {
        "success": True,
        "message": "Reward claimed successfully!",
        "telegram_id": telegram_id,
        "reward_amount": 100
    }


@app.get("/api/user-balance/{telegram_id}")
async def get_user_balance(telegram_id: int):
    """
    Retrieves the current token balance for a user.
    """
    # TODO: Fetch balance from your database (e.g., Supabase, PostgreSQL)
    return {
        "telegram_id": telegram_id,
        "balance": 500  # Replace with actual DB lookup value
    }
