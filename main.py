import hmac
import hashlib
import urllib.parse

def verify_telegram_webapp_data(init_data: str, bot_token: str) -> bool:
    """Validates Telegram WebApp initData against the bot token."""
    if not bot_token or not init_data:
        return False

    try:
        parsed_data = urllib.parse.parse_qs(init_data)
        if "hash" not in parsed_data:
            return False

        received_hash = parsed_data.pop("hash")[0]

        # Construct data check string (sorted keys with key=value joined by newlines)
        items = sorted([(k, v[0]) for k, v in parsed_data.items()])
        data_check_string = "\n".join([f"{k}={v}" for k, v in items])

        # Calculate secret key using SHA256 HMAC of bot token with key "WebAppData"
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
        ).digest()

        # Calculate hash of data_check_string using the secret_key
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # Securely compare hashes
        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception:
        return False  
        received_hash = parsed_data.pop("hash")
        
        # Construct data check string
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        # Calculate secret key and HMAC hash
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception:
        return False

# --- API Endpoints ---

@app.get("/")
async def read_root():
    return {
        "status": "online",
        "service": "TMX-QUANTUM API",
        "message": "FastAPI engine is running smoothly"
    }

@app.post("/api/claim-reward")
async def grant_reward(payload: RewardClaimRequest):
    # Allow bypass during development if initData is sent
    if payload.initData:
        is_valid = verify_telegram_data(payload.initData)
        if not is_valid:
    # Grant default reward amount
    return {
        "success": True,
        "message": "Reward claimed successfully",
        "reward_amount": 100
    }
