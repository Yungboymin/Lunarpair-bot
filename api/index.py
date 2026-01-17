import logging
import asyncio
from fastapi import FastAPI, Request
from telethon import TelegramClient, StringSession, connection
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# 1. SETUP LOGGING (Critical for Vercel)
logging.basicConfig(
    format='%(levelname)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("lunar_bot")

app = FastAPI()

# Credentials
API_ID = 36531006
API_HASH = '8b4df3bdc80ff44b80a1d788d4e55eb2'
MONGO_URI = "mongodb+srv://eternlxz516_db_user:1asJy8YrLKj4cL73@lunar.6ltkilo.mongodb.net/?appName=Lunar"

@app.post("/api/send_code")
async def send_code(data: Request):
    try:
        body = await data.json()
        phone = body.get("phone")
        user_id = str(body.get("user_id"))

        logger.info(f"--- New Request ---")
        logger.info(f"User: {user_id} | Phone: {phone}")

        # 2. OPTIMIZED CLIENT
        client = TelegramClient(
            StringSession(), 
            API_ID, 
            API_HASH,
            connection=connection.ConnectionTcpFull, # cloud
            connection_retries=1
        )

        logger.info("Connecting to Telegram...")
        # a 
        await asyncio.wait_for(client.connect(), timeout=12.0)
        logger.info("Connected successfully.")

        logger.info("Requesting code...")
        sent = await client.send_code_request(phone)
        logger.info(f"Code sent! Hash: {sent.phone_code_hash}")

        # 3. DB CONNECTION 
        logger.info("Connecting to MongoDB...")
        db_client = AsyncIOMotorClient(MONGO_URI)
        db = db_client["lunar_db"]
        
        await db.temp_sessions.update_one(
            {"user_id": user_id},
            {"$set": {
                "phone": phone,
                "hash": sent.phone_code_hash,
                "createdAt": datetime.utcnow()
            }},
            upsert=True
        )
        logger.info("Data saved to MongoDB.")

        await client.disconnect()
        return {"status": "success"}

    except asyncio.TimeoutError:
        logger.error("TIMEOUT: Telegram connection took too long (Serverless Limit)")
        return {"status": "error", "message": "Connection timeout. Please try again."}
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {str(e)}")
        return {"status": "error", "message": str(e)}

# Export  Vercel
handler = app
