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

# 1. Fetch Telegram Bot Token safely from Vercel Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# 2. Initialize FastAPI Application
app = FastAPI(title="TMX Quantum API", version="1.0.0")

# 3. Enable CORS (Allows your frontend to communicate with this backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Data Models ---
class RewardRequest(BaseModel):
    initData: str  # Raw initData query string sent from Telegram WebApp SDK


# --- Helper Functions ---
def verify_telegram_data(init_data: str) -> bool:
    """
    Validates initData hash using HMAC-SHA256 and TELEGRAM_TOKEN.
    """
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN environment variable is missing.")
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


# --- Routes ---

@app.get("/")
async def root():
    """Health check endpoint to verify backend status."""
    return {
        "status": "online",
        "service": "TMX Quantum API",
        "message": "FastAPI engine is running smoothly!"
    }


@app.post("/api/grant-reward")
async def grant_reward(payload: RewardRequest):
    """
    Validates Telegram user authentication and processes ad rewards.
    """
    if not payload.initData:
        raise HTTPException(status_code=400, detail="Missing initData in request payload.")

    # Validate hash signature against Telegram Bot Token
    is_valid = verify_telegram_data(payload.initData)
    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid Telegram authentication payload.")

    # Parse user details safely
    parsed_data = dict(parse_qsl(payload.initData))
    user_info = json.loads(parsed_data.get("user", "{}"))
    user_id = user_info.get("id")

    # TODO: Add your database/token minting logic here (e.g., increment user balance)
    
    return {
        "success": True,
        "message": "Reward claimed successfully!",
        "user_id": user_id,
        "amount_earned": 100  # Adjust as needed
    }
