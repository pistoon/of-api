from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import hashlib
import time
import json
import os
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth data - będziemy tu wklejać z przeglądarki
AUTH = {
    "cookie": os.environ.get("OF_COOKIE", ""),
    "user_agent": os.environ.get("OF_USER_AGENT", ""),
    "x_bc": os.environ.get("OF_XBC", ""),
    "user_id": os.environ.get("OF_USER_ID", "")
}

HEADERS_BASE = {
    "Accept": "application/json, text/plain, */*",
    "App-Token": "33d57ade8c02dbc5a333db99ff9ae26a",
    "User-Agent": AUTH["user_agent"],
    "x-bc": AUTH["x_bc"],
    "Cookie": AUTH["cookie"],
}

async def get_signed_headers(url: str):
    """Generuje podpisane headery dla OF API"""
    # Dynamic rules endpoint - publiczny
    async with httpx.AsyncClient() as client:
        rules_resp = await client.get(
            "https://raw.githubusercontent.com/mikigoalie/onlyfans-rulegen/main/rules.json"
        )
        rules = rules_resp.json()
    
    ts = str(int(time.time() * 1000))
    
    # Generujemy sign hash
    msg = "\n".join([rules["static_param"], ts, url, AUTH["user_id"]])
    sign = hashlib.sha1(msg.encode()).hexdigest()
    prefix = rules.get("prefix", "")
    suffix = rules.get("suffix", "")
    checksum_indexes = rules.get("checksum_indexes", [])
    checksum_constant = rules.get("checksum_constant", 0)
    
    checksum = sum(ord(sign[i]) for i in checksum_indexes) + checksum_constant
    
    headers = {
        **HEADERS_BASE,
        "sign": f"{prefix}:{sign}:{abs(checksum):x}:{suffix}",
        "time": ts,
    }
    return headers

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/chats")
async def get_chats(filter: str = "unread", limit: int = 20):
    url = f"/api2/v2/chats?limit={limit}&filter={filter}"
    headers = await get_signed_headers(url)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://onlyfans.com{url}", headers=headers)
    return resp.json()

@app.get("/fans")
async def get_fans(limit: int = 20, offset: int = 0):
    url = f"/api2/v2/subscriptions/subscribers?limit={limit}&offset={offset}&type=active"
    headers = await get_signed_headers(url)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://onlyfans.com{url}", headers=headers)
    return resp.json()

@app.get("/messages/{chat_id}")
async def get_messages(chat_id: int, limit: int = 10):
    url = f"/api2/v2/chats/{chat_id}/messages?limit={limit}&order=desc"
    headers = await get_signed_headers(url)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://onlyfans.com{url}", headers=headers)
    return resp.json()

class MessageBody(BaseModel):
    text: str

@app.post("/send/{chat_id}")
async def send_message(chat_id: int, body: MessageBody):
    url = f"/api2/v2/chats/{chat_id}/messages"
    headers = await get_signed_headers(url)
    headers["Content-Type"] = "application/json"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://onlyfans.com{url}",
            headers=headers,
            json={"text": body.text, "locked": False, "isCouplePeopleMedia": False}
        )
    return resp.json()

class DeleteBody(BaseModel):
    message_id: int

@app.delete("/message/{chat_id}/{message_id}")
async def delete_message(chat_id: int, message_id: int):
    url = f"/api2/v2/chats/{chat_id}/messages/{message_id}"
    headers = await get_signed_headers(url)
    async with httpx.AsyncClient() as client:
        resp = await client.delete(f"https://onlyfans.com{url}", headers=headers)
    return resp.json()
