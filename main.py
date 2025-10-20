import flask
from flask import Flask, request, jsonify
import asyncio
import os
import time
import sys
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, UserChannelsTooMuch, UserDeactivated, PeerIdInvalid, InviteHashInvalid

app = Flask(__name__)

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_string = os.getenv("SESSION_STRING")
default_chat_id = os.getenv("CHAT_ID")

CONCURRENCY = 20
async def process_username(username):
    async with Client("fast_approver", api_id=api_id, api_hash=api_hash, session_string=session_string) as app:
        try:
            chat = await app.get_chat(username)
            chat_id = chat.id
            join_requests = [req async for req in app.get_chat_join_requests(chat_id)]
            approved = 0
            skipped = 0
            for i in range(0, len(join_requests), CONCURRENCY):
                batch = join_requests[i:i+CONCURRENCY]
                tasks = [approve_user(app, chat_id, req.user) for req in batch]
                results = await asyncio.gather(*tasks)
                approved += results.count("approved")
                skipped += results.count("skipped")
            return {"status": "success", "approved": approved, "skipped": skipped}
        except InviteHashInvalid:
            return {"status": "error", "message": "Invalid invite or username"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

async def leave_chat(chat_identifier):
    async with Client("fast_approver", api_id=api_id, api_hash=api_hash, session_string=session_string) as app:
        try:
            chat = await app.get_chat(chat_identifier)
            await app.leave_chat(chat.id)
            return {
                "status": "left",
                "chat_title": chat.title,
                "chat_id": chat.id
            }
        except PeerIdInvalid:
            return {
                "status": "error",
                "message": f"Peer id invalid: {chat_identifier}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

@app.route('/leave', methods=['POST'])
def leave():
    data = request.get_json()
    chat_id = data.get("chat_id")
    if not chat_id:
        return jsonify({"status": "error", "message": "Missing 'chat_id'"}), 400

    try:
        result = asyncio.run(leave_chat(chat_id))
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(main(default_chat_id))
    return jsonify({"status": "done", "result": result})

async def join_only(invite_link):
    async with Client("fast_approver", api_id=api_id, api_hash=api_hash, session_string=session_string) as app:
        try:
            chat = await app.join_chat(invite_link)
            return {"status": "joined", "title": chat.title, "id": chat.id}
        except InviteHashInvalid:
            return {"status": "error", "message": "Invalid invite link"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@app.route('/receive', methods=['POST'])
def receive():
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"status": "error", "message": "Missing 'username'"}), 400
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(join_only(username))
    return jsonify(result)

@app.route('/accept', methods=['POST'])
def accept():
    data = request.get_json()
    raw = data.get("username")
    if not raw:
        return jsonify({"status": "error", "message": "Missing 'username'"}), 400

    if isinstance(raw, str) and raw.lstrip('-').isdigit():
        try:
            chat_ref = int(raw)
        except ValueError:
            return jsonify({"status": "error", "message": "Invalid chat ID format"}), 400
    else:
        chat_ref = raw

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(process_username(chat_ref))
    return jsonify(result)

# ------------------ CLI entrypoint ------------------
async def _cli(query: str):
    res = await extractWormGPT(query)
    print(res or "")

# ------------------ Main ------------------
if __name__ == "__main__":
        app.run(host="0.0.0.0", port=3000, debug=True)
