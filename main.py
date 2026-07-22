import os
import hashlib
import hmac
import json
from urllib.parse import parse_qsl
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="TMX Quantum Backend",
    version="1.0.0",
    description="Backend server for TMX Quantum Telegram authentication"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Securely load token from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

class TelegramAuthData(BaseModel):
    initData: str

@app.get("/")
def read_root():
    return {
        "status": "Online",
        "service": "TMX Quantum Backend",
        "message": "FastAPI server is live and running successfully."
    }

@app.post("/api/auth/telegram")
def verify_telegram_auth(data: TelegramAuthData):
    try:
        if not TELEGRAM_BOT_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Telegram bot token not configured on server."
            )
            
        parsed_data = dict(parse_qsl(data.initData))
        received_hash = parsed_data.pop('hash', None)
        
        if not received_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Hash is missing from initData."
            )

        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(parsed_data.items())
        )

        secret_key = hmac.new(
            b"WebAppData", 
            TELEGRAM_BOT_TOKEN.encode(), 
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key, 
            data_check_string.encode(), 
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature."
            )

        user_info = json.loads(parsed_data.get('user', '{}'))
        return {
            "status": "success",
            "message": "Telegram authentication verified successfully.",
            "user": user_info
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid authentication payload: {str(e)}"
        )
