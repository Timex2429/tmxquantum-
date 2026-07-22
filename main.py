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

# Enable CORS so your frontend/Mini App can communicate freely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Your Telegram Bot Token
TELEGRAM_BOT_TOKEN = "8792544712:AAE8jprlzjBnrDJpbVpCKDAOwxFS-NGHOQc"

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
    """
    Validates the initData string received from the Telegram WebApp SDK.
    """
    try:
        parsed_data = dict(parse_qsl(data.initData))
        received_hash = parsed_data.pop('hash', None)
        
        if not received_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Hash is missing from initData."
            )

        # Sort the remaining parameters alphabetically and format as key=value
        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(parsed_data.items())
        )

        # Compute the secret key using WebAppData and the bot token
        secret_key = hmac.new(
            b"WebAppData", 
            TELEGRAM_BOT_TOKEN.encode(), 
            hashlib.sha256
        ).digest()

        # Compute the signature hash
        calculated_hash = hmac.new(
            secret_key, 
            data_check_string.encode(), 
            hashlib.sha256
        ).hexdigest()

        # Secure comparison of hashes
        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature."
            )

        # Authentication successful
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
