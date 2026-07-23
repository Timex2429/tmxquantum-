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
    
@app.post("/api/claim-rewards")
async def claim_rewards(data: dict):
        telegram_id = data.get("telegramId")

    telegram_id = data.get("telegramId")
    
    # Find user in MongoDB and transfer rewards to balance
    user = await users_collection.find_one({"telegramId": telegram_id})
    if not user or user.get("rewardsEarned", 0) <= 0:
        raise HTTPException(status_code=400, detail="No rewards available to claim")
    
    claimed_amount = user["rewardsEarned"]
    new_balance = user.get("balance", 0) + claimed_amount
    
    # Update database: add to balance, reset rewards to 0
    await users_collection.update_one(
        {"telegramId": telegram_id},
        {"$set": {"balance": new_balance, "rewardsEarned": 0}}
    )
    
    return {
        "success": True, 
        "newBalance": new_balance, 
        "claimedAmount": claimed_amount
    }
    @app.post("/api/process-referral")
async def process_referral(data: dict):
    telegram_id = data.get("telegramId")
    referrer_id = data.get("referrerId")

    if not referrer_id or telegram_id == referrer_id:
        return {"success": False, "message": "Invalid referral"}

    # Check if this user already registered a referral
    user = await users_collection.find_one({"telegramId": telegram_id})
    if user and user.get("referredBy"):
        return {"success": False, "message": "Already referred"}

    # Mark user as referred and reward referrer
    await users_collection.update_one(
        {"telegramId": telegram_id},
        {"$set": {"referredBy": referrer_id}},
        upsert=True
    )

    # Give bonus to the referrer (e.g., 100 TMX)
    await users_collection.update_one(
        {"telegramId": referrer_id},
        {"$inc": {"balance": 100.0}}
    )

    return {"success": True, "message": "Referral processed successfully"}

