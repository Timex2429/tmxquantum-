import os
import hashlib
import hmac
import json
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
    id: int
    first_name: str
    username: str = None
    photo_url: str = None
    auth_date: int
    hash: str

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
            
        # Convert incoming data to dict and remove the hash for validation checking
        auth_data = data.dict(exclude_unset=True)
        received_hash = auth_data.pop('hash', None)
        
        if not received_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Hash is missing."
            )

        # Sort parameters alphabetically and format as key=value
        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(auth_data.items()) if v is not None
        )

        # Compute secret key using SHA256 of the bot token
        secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()

        # Compute signature hash
        calculated_hash = hmac.new(
            secret_key, 
            data_check_string.encode(), 
            hashlib.sha256
        ).hexdigest()

        # Verify hash
        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature."
            )

        return {
            "status": "success",
            "message": "Telegram authentication verified successfully.",
            "user": {
                "id": data.id,
                "first_name": data.first_name,
                "username": data.username
            }
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid authentication payload: {str(e)}"
        )
