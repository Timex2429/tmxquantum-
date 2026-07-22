import os
import hashlib
import hmac
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables if a .env file is present locally
load_dotenv()

app = FastAPI(title="TMX Quantum Backend", version="1.0.0")

# Enable CORS for frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, etc.
    allow_headers=["*"],
)

# Fetch your Telegram Bot Token from environment variables (set these on Render)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    username: str = None
    photo_url: str = None
    auth_date: int
    hash: str

@app.get("/")
def read_root():
    return {"status": "online", "message": "TMX Quantum Backend is running successfully!"}

@app.post("/api/auth/telegram")
def verify_telegram_auth(data: TelegramAuthData):
    """
    Verifies the data received from Telegram Login Widget or WebApp data.
    """
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Telegram bot token not configured on server.")

    # Convert request data to a dictionary, omitting the hash for validation
    auth_data = data.dict()
    received_hash = auth_data.pop("hash")
    
    # Sort keys alphabetically and format as 'key=value'
    data_check_string = "\n".join(
        [f"{k}={v}" for k, v in sorted(auth_data.items()) if v is not None]
    )

    # Calculate secret key using SHA256 on the bot token
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    
    # Calculate HMAC-SHA256 signature
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    # Compare hashes securely
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid Telegram authentication signature.")

    # Authentication successful — handle your user login/registration logic here
    return {
        "success": True, 
        "message": "Authentication verified successfully", 
        "user_id": data.id
    }
