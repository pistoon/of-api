from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import hashlib
import time
import os
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH = {
    "cookie": os.environ.get("OF_COOKIE", ""),
    "user_agent": os.environ.get("OF_USER_AGENT", ""),
    "x_bc": os.environ.get("OF_XBC", ""),
    "user_id": os.environ.get("OF_USER_ID", "")
}

async def get_signed_headers(url: str):
    async with httpx.AsyncClient() as client:
        rules_resp = await client.get(
            "https://raw.githubusercontent.com/mikigoalie/onlyfans-rulegen/main/rules.json",
            timeout=10
        )
        rules = rules_resp.json()
    ts = str(int(time.time() * 1000))
    msg = "\n".join([rules["static_param"], ts, url, AUTH["user_id"]])
    sign = hashlib.sha1(msg.encode()).hexdigest()
    prefix = rules.get("prefix", "")
    suffix = rules.get("suffix", "")
    checksum_indexes = rules.get("checksum_indexes", [])
    checksum_constant = rules.get("checksum_constant", 0)
    checksum = sum(ord(sign[i]) for i in checksum_indexes) + checksum_constant
    return {
        "Accept": "application/json, text/plain, */*",
        "App-Token": "33d57ade8c02dbc5a333db99ff9ae26a",
        "User-Agent": AUTH["user_agent"],
        "x-bc": AUTH["x_bc"],
        "Cookie": AUTH["cookie"],
