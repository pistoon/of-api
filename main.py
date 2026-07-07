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
        "sign": f"{prefix}:{sign}:{abs(checksum):x}:{suffix}",
        "time": ts,
    }

async def of_get(url: str):
    headers = await get_signed_headers(url)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://onlyfans.com{url}", headers=headers, timeout=15)
    return resp.json()

async def of_post(url: str, data: dict):
    headers = await get_signed_headers(url)
    headers["Content-Type"] = "application/json"
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"https://onlyfans.com{url}", headers=headers, json=data, timeout=15)
    return resp.json()

async def of_delete(url: str):
    headers = await get_signed_headers(url)
    async with httpx.AsyncClient() as client:
        resp = await client.delete(f"https://onlyfans.com{url}", headers=headers, timeout=15)
    return resp.json()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/mcp")
async def mcp_info():
    return {"name": "Stella OF API", "version": "1.0.0"}

@app.post("/mcp")
async def mcp_handler(request: Request):
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})
    req_id = body.get("id", 1)

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "stella-of-api", "version": "1.0.0"}}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [
            {"name": "get_chats", "description": "Get chats", "inputSchema": {"type": "object", "properties": {"filter": {"type": "string", "default": "unread"}, "limit": {"type": "integer", "default": 20}}}},
            {"name": "get_fans", "description": "Get active fans", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}, "offset": {"type": "integer", "default": 0}}}},
            {"name": "get_messages", "description": "Get messages from chat", "inputSchema": {"type": "object", "properties": {"chat_id": {"type": "integer"}, "limit": {"type": "integer", "default": 5}}, "required": ["chat_id"]}},
            {"name": "send_message", "description": "Send message to fan", "inputSchema": {"type": "object", "properties": {"chat_id": {"type": "integer"}, "text": {"type": "string"}}, "required": ["chat_id", "text"]}},
            {"name": "delete_message", "description": "Delete a message", "inputSchema": {"type": "object", "properties": {"chat_id": {"type": "integer"}, "message_id": {"type": "integer"}}, "required": ["chat_id", "message_id"]}},
        ]}}

    if method == "tools/call":
        tool = params.get("name")
        args = params.get("arguments", {})
        try:
            if tool == "get_chats":
                result = await of_get(f"/api2/v2/chats?limit={args.get('limit',20)}&filter={args.get('filter','unread')}")
            elif tool == "get_fans":
                result = await of_get(f"/api2/v2/subscriptions/subscribers?limit={args.get('limit',20)}&offset={args.get('offset',0)}&type=active")
            elif tool == "get_messages":
                result = await of_get(f"/api2/v2/chats/{args['chat_id']}/messages?limit={args.get('limit',5)}&order=desc")
            elif tool == "send_message":
                result = await of_post(f"/api2/v2/chats/{args['chat_id']}/messages", {"text": args["text"], "locked": False, "isCouplePeopleMedia": False})
            elif tool == "delete_message":
                result = await of_delete(f"/api2/v2/chats/{args['chat_id']}/messages/{args['message_id']}")
            else:
                result = {"error": "Unknown tool"}
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(result)}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}
