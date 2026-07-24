from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import hashlib
import hmac
from urllib.parse import parse_qsl

app = FastAPI()

# Enable CORS so your frontend and backend communicate smoothly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# Telegram Authentication & Validation Setup
# ==========================================

# Your actual Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN = "8792544712:AAE8jprlzjBnrDJpbVpCKDAOwxFS-NGHOQc"

def verify_telegram_init_data(init_data: str, bot_token: str) -> bool:
    """Validates the initData string sent from Telegram WebApp SDK."""
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
            digestmod=hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            key=secret_key, 
            msg=data_check_string.encode(), 
            digestmod=hashlib.sha256
        ).hexdigest()

        # Securely compare hashes to prevent timing attacks
        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception:
        return False


# ==========================================
# Routes & Endpoints
# ==========================================

@app.get("/")
async def serve_frontend():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"status": "Online", "message": "Backend is running!"}
