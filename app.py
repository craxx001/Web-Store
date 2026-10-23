from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.message import DecodeError
import os

app = Flask(__name__)

CORS(app, resources={
    r"/*": {
        "origins": "*"
    }
})

# ============================================================
# API KEY PROTECTION
# Set API_KEY in Vercel Environment Variables.
# Example value: a long random secret.
# ============================================================
API_KEY = ("API_KEY", "NRZ200").strip()

def is_valid_api_key():
    supplied_key = request.args.get("key", "").strip()
    return bool(API_KEY) and supplied_key == API_KEY

def load_tokens():
    try:
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
        return tokens
    except Exception as e:
        app.logger.error(f"Error loading tokens: {e}")
        return None

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Error encrypting message: {e}")
        return None

def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating protobuf message: {e}")
        return None

async def send_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2022.3.47f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB55"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers) as response:
                if response.status != 200:
                    app.logger.error(f"Request failed with status code: {response.status}")
                    return response.status
                return await response.text()
    except Exception as e:
        app.logger.error(f"Exception in send_request: {e}")
        return None

async def send_multiple_requests(uid, server_name, url):
    try:
        region = server_name
        protobuf_message = create_protobuf_message(uid, region)
        if protobuf_message is None:
            app.logger.error("Failed to create protobuf message.")
            return None
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None:
            app.logger.error("Encryption failed.")
            return None
        tasks = []
        tokens = load_tokens()
        if tokens is None:
            app.logger.error("Failed to load tokens.")
            return None
        for i in range(100):
            token = tokens[i % len(tokens)]["token"]
            tasks.append(send_request(encrypted_uid, token, url))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    except Exception as e:
        app.logger.error(f"Exception in send_multiple_requests: {e}")
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating uid protobuf: {e}")
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    encrypted_uid = encrypt_message(protobuf_data)
    return encrypted_uid

def make_request(encrypt, server_name, token):
    try:
        url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2022.3.47f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB55"
        }
        response = requests.post(url, data=edata, headers=headers, timeout=15)
        hex_data = response.content.hex()
        binary = bytes.fromhex(hex_data)
        decode = decode_protobuf(binary)
        if decode is None:
            app.logger.error("Protobuf decoding returned None.")
        return decode
    except Exception as e:
        app.logger.error(f"Error in make_request: {e}")
        return None

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except DecodeError as e:
        app.logger.error(f"Error decoding Protobuf data: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error during protobuf decoding: {e}")
        return None

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "API is running", "endpoint": "/like?uid=<uid>&key=<api_key>"})

@app.route('/like', methods=['GET'])
def handle_requests():
    if not is_valid_api_key():
        return jsonify({"error": "Invalid or missing API key", "Status": 3}), 401

    uid = request.args.get("uid", "").strip()
    if not uid.isdigit() or not (7 <= len(uid) <= 13):
        return jsonify({"error": "A valid UID is required", "Status": 3}), 400

    try:
        tokens = load_tokens()
        if not isinstance(tokens, list) or not tokens or any(
            not isinstance(item, dict) or not item.get("token") for item in tokens
        ):
            return jsonify({"error": "Add valid tokens to tokens.json", "Status": 3}), 500

        token = tokens[0]["token"]
        encrypted_uid = enc(uid)
        if encrypted_uid is None:
            return jsonify({"error": "UID encryption failed", "Status": 3}), 500

        before = make_request(encrypted_uid, "IND", token)
        if before is None:
            return jsonify({"error": "Unable to retrieve player information", "Status": 3}), 502

        before_data = json.loads(MessageToJson(before))
        before_info = before_data.get("AccountInfo", {})
        before_like = int(before_info.get("Likes", 0) or 0)

        url = "https://client.ind.freefiremobile.com/LikeProfile"
        asyncio.run(send_multiple_requests(uid, "IND", url))

        after = make_request(encrypted_uid, "IND", token)
        if after is None:
            return jsonify({"error": "Unable to retrieve player information after request", "Status": 3}), 502

        after_data = json.loads(MessageToJson(after))
        after_info = after_data.get("AccountInfo", {})
        after_like = int(after_info.get("Likes", 0) or 0)
        player_uid = int(after_info.get("UID", uid) or uid)
        player_name = str(after_info.get("PlayerNickname", "") or "")
        given = max(0, after_like - before_like)

        return jsonify({
            "Nickname": player_name,
            "UID": player_uid,
            "After": after_like,
            "Before": before_like,
            "Given": given,
            "Status": 1 if given > 0 else 2
        })
    except Exception:
        app.logger.exception("Request processing failed")
        return jsonify({"error": "Request processing failed", "Status": 3}), 500

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False)
