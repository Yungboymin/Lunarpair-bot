from fastapi import FastAPI, Request
from telethon import TelegramClient, StringSession
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import os

app = FastAPI()

# Credentials
API_ID = 36531006
API_HASH = '8b4df3bdc80ff44b80a1d788d4e55eb2'
MONGO_URI = "mongodb+srv://eternlxz516_db_user:1asJy8YrLKj4cL73@lunar.6ltkilo.mongodb.net/?appName=Lunar"

db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["lunar_db"]

@app.post("/api/send_code")
async def send_code(data: Request):
    body = await data.json()
    phone = body.get("phone")
    user_id = str(body.get("user_id"))
    
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    
    try:
        sent = await client.send_code_request(phone)
        
        # Save attempt with a timestamp for the 1-minute auto-delete
        await db.temp_sessions.update_one(
            {"user_id": user_id},
            {"$set": {
                "phone": phone,
                "hash": sent.phone_code_hash,
                "createdAt": datetime.utcnow() # MongoDB uses this to count the 60 seconds
            }},
            upsert=True
        )
        
        await client.disconnect()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/verify")
async def verify(data: Request):
    body = await data.json()
    user_id = str(body.get("user_id"))
    code = body.get("code")
    password = body.get("password")

    # Check if the attempt still exists (hasn't been deleted by the 1-min timer)
    s_data = await db.temp_sessions.find_one({"user_id": user_id})
    if not s_data:
        return {"status": "error", "message": "Time expired (1 min). Please request a new code."}

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()

    try:
        # Attempt sign in
        await client.sign_in(s_data["phone"], code, phone_code_hash=s_data["hash"])
        
        # Handle 2FA
        if not await client.is_user_authorized():
            if password:
                await client.sign_in(password=password)
            else:
                return {"status": "2fa_required"}

        # Success! Save permanent session
        session_str = client.session.save()
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"session": session_str, "status": "active", "paired_at": datetime.utcnow()}},
            upsert=True
        )
        
        # Manually delete temp data since we are finished
        await db.temp_sessions.delete_one({"user_id": user_id})
        await client.disconnect()
        
        return {"status": "success"}

    except Exception as e:
        if "password" in str(e).lower():
            return {"status": "2fa_required"}
        return {"status": "error", "message": str(e)}
