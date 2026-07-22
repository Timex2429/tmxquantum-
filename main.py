import os
import hashlib
import hmac
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="TMX Quantum Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    username: str = None
    photo_url: str = None
    auth_date: int
    hash: str

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>TMX Quantum Backend</title>
            <style>
                body { font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                .card { background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); text-align: center; max-width: 400px; width: 100%; }
                h1 { color: #38bdf8; font-size: 24px; margin-bottom: 10px; }
                p { color: #94a3b8; font-size: 14px; }
                .badge { display: inline-block; background: #065f46; color: #34d399; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-top: 15px; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>TMX Quantum Backend</h1>
                <p>Your FastAPI server is live and running successfully on Render.</p>
                <div class="badge">Status: Online</div>
            </div>
        </body>
    </html>
    """

@app.post("/api/auth/telegram")
def verify_telegram_auth(data: TelegramAuthData):
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Token not configured.")
    auth_data = data.dict()
    received_hash = auth_data.pop("hash")
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(auth_data.items()) if v is not None])
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid signature.")
    return {"success": True, "message": "Verified", "user_id": data.id}
