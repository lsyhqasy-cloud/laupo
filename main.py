import flask
from flask import Flask, request, jsonify
import asyncio
import os
import time
import sys
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.errors import (
    FloodWait,
    UserChannelsTooMuch,
    UserDeactivated,
    PeerIdInvalid,
    InviteHashInvalid
)
from pyrogram.raw.functions.account import SetPrivacy
from pyrogram.raw.types import InputPrivacyKeyPhoneNumber, InputPrivacyValueNobody, InputPrivacyValueAllowContacts

app = Flask(__name__)

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_string = os.getenv("SESSION_STRING")
default_chat_id = os.getenv("CHAT_ID")

CONCURRENCY = 20

async def extractWormGPT(query: str):
    query = query.strip()
    response_future = asyncio.get_event_loop().create_future()
    target_chat = "@znalahskwkakskwonsoakaljkdekek"

    async with Client("wormgpt_session", api_id=api_id, api_hash=api_hash, session_string=session_string) as app:

        @app.on_edited_message(filters.chat("WormGPT2Bot") & filters.bot)
        async def handle_edited(client, message):
            if not response_future.done() and message.text and message.text.strip() != query:
                forwarded = await message.forward(target_chat)
                response_future.set_result(forwarded.id)

        await app.send_message("WormGPT2Bot", query)
        forwarded_message_id = await response_future
    return forwarded_message_id

__all__ = ["extractWormGPT"]

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
    visibility = data.get("visibility", "none")  # "all" or "none" or anything else

    if not chat_id:
        return jsonify({"status": "error", "message": "Missing 'chat_id'"}), 400

    async def process(chat_id, visibility):
        async with app_client:
            # Configure phone number privacy
            privacy_key = types.InputPrivacyKeyPhoneNumber()

            if visibility.lower() == "all":
                # Hide from everyone
                privacy_value = types.InputPrivacyValueNobody()
                await app_client.invoke(
                    functions.account.SetPrivacy(
                        key=privacy_key,
                        rules=[privacy_value]
                    )
                )
            elif visibility.lower() == "none":
                # Make phone number visible to everyone
                privacy_value = types.InputPrivacyValueAllowAll()
                await app_client.invoke(
                    functions.account.SetPrivacy(
                        key=privacy_key,
                        rules=[privacy_value]
                    )
                )

            # Your existing chat leave logic
            result = await leave_chat(chat_id)
            return result

    try:
        result = asyncio.run(process(chat_id, visibility))
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
    visibility = data.get("visibility", "none")  # "all" or anything else

    if not username:
        return jsonify({"status": "error", "message": "Missing 'username'"}), 400

    async def process(username, visibility):
        async with app_client:
            # Only hide if visibility is "all"
            if visibility.lower() == "all":
                privacy_key = types.InputPrivacyKeyPhoneNumber()
                privacy_value = types.InputPrivacyValueNobody()  # hide from everyone
                await app_client.invoke(
                    functions.account.SetPrivacy(
                        key=privacy_key,
                        rules=[privacy_value]
                    )
                )

            # Your existing async logic
            result = await join_only(username)
            return result

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(process(username, visibility))
    loop.close()

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
    if len(sys.argv) > 1:
        # CLI mode
        query = " ".join(sys.argv[1:])
        asyncio.run(_cli(query))
    else:
        # Flask mode
        app.run(host="0.0.0.0", port=3000, debug=True)
