from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI()

# Enable CORS so your frontend and backend communicate without blocks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Route to serve your index.html frontend file at the root URL
@app.get("/")
async def serve_frontend():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"status": "Online", "message": "Backend is running, but index.html was not found."}

# 2. Example model for your Telegram authentication payload
class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    username: str | None = None
    hash: str

# 3. Your Telegram authentication endpoint
@app.post("/api/auth/telegram")
async def authenticate_telegram(data: TelegramAuthData):
    # Add your telegram validation / token verification logic here
    return {
        "success": True,
        "message": f"Successfully authenticated user {data.first_name}!"
    }
