import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from io import BytesIO
from urllib.parse import urlencode

import qrcode
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from telegram import (
    Update, BotCommand, BotCommandScopeChat, BotCommandScopeDefault,
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters,
)

load_dotenv()

# ============================================================
# CONFIG
# ============================================================
DB_FILE = Path(os.getenv("DB_FILE", "database.json"))
IST = pytz.timezone("Asia/Kolkata")
TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
OWNER_IDS = [int(x.strip()) for x in os.getenv("OWNER_IDS", "8853678390").split(",") if x.strip().isdigit()]

DEFAULT_CONFIG = {
    "upi_id": "sandeepshoww@oksbi",
    "upi_name": "NRZ RAVI",
    "admin_contact": "@nrzravi",
    "help_text": (
        "❓ <b>Help & Support</b>\n\n"
        "<b>How to use the bot:</b>\n"
        "• ❤️ Autolikes – Select package, region, enter UID and complete payment.\n"
        "• 🏆 Guild Glory Bot – Select package, region, enter UID and complete payment.\n"
        "• 🛒 Purchase ID – Select a package, pay and send the payment proof.\n"
        "• 📦 My Orders – Check approved active orders and their status.\n\n"
        "For payment verification or any issue, contact admin."
    ),
    "how_to_pay_url": "",
    "daily_run_time": "4:00 AM IST",
    "autolike_packages": [
        {"id": "a1", "name": "⚡ ₹45 — 1 Day » 500 Likes", "price": 45, "days": 1, "likes": 500, "active": True},
        {"id": "a2", "name": "💥 ₹150 — 7 Day » 3500 Likes", "price": 150, "days": 7, "likes": 3500, "active": True},
        {"id": "a3", "name": "💥 ₹240 — 15 Day » 7500 Likes", "price": 240, "days": 15, "likes": 7500, "active": True},
        {"id": "a4", "name": "🔥 ₹500 — 30 Day » 15000 Likes", "price": 500, "days": 30, "likes": 15000, "active": True},
        {"id": "a5", "name": "👑 ₹1000 — 60 Day » 30000 Likes", "price": 1000, "days": 60, "likes": 30000, "active": True},
    ],
    "glory_packages": [
        {"id": "g1", "name": "🏆 ₹100 — 1 Day", "price": 100, "days": 1, "active": True},
        {"id": "g2", "name": "🏆 ₹500 — 7 Day", "price": 500, "days": 7, "active": True},
        {"id": "g3", "name": "🏆 ₹900 — 15 Day", "price": 900, "days": 15, "active": True},
        {"id": "g4", "name": "🏆 ₹1600 — 30 Day", "price": 1600, "days": 30, "active": True},
    ],
    "purchase_packages": [],
}

REGIONS = [
    ("IND", "IND"), ("BR", "BR"), ("US", "US"),
    ("SAC", "SAC"), ("NA", "NA"), ("SG", "SG"),
    ("RU", "RU"), ("ID", "ID"), ("TW", "TW"),
    ("VN", "VN"), ("TH", "TH"), ("ME", "ME"),
    ("PK", "PK"), ("CIS", "CIS"), ("BD", "BD"),
    ("EUROPE", "EUROPE"),
]
REGION_NAMES = dict(REGIONS)


def now_ist():
    return datetime.now(IST)


def iso_now():
    return now_ist().strftime("%Y-%m-%d %H:%M:%S")


def is_owner(user_id):
    return int(user_id) in OWNER_IDS


def uid_ok(text):
    return bool(re.fullmatch(r"\d{6,15}", text.strip()))


def utr_ok(text):
    return bool(re.fullmatch(r"[A-Za-z0-9]{6,40}", text.strip()))


def money(v):
    try:
        n = float(v)
    except Exception:
        n = 0
    return f"{n:.2f}".rstrip("0").rstrip(".")


def new_db():
    return {
        "config": json.loads(json.dumps(DEFAULT_CONFIG)),
        "users": {},
        "orders": [],
        "stats": {"total_orders": 0},
    }


def deep_merge(default, existing):
    if isinstance(default, dict):
        out = dict(default)
        if isinstance(existing, dict):
            for k, v in existing.items():
                if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                    out[k] = deep_merge(out[k], v)
                else:
                    out[k] = v
        return out
    return existing if existing is not None else default


def load_db():
    if not DB_FILE.exists():
        return new_db()
    try:
        return deep_merge(new_db(), json.loads(DB_FILE.read_text(encoding="utf-8")))
    except Exception:
        return new_db()


db = load_db()


def save_db():
    tmp = DB_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DB_FILE)


def user_record(user):
    key = str(user.id)
    if key not in db["users"]:
        db["users"][key] = {
            "id": user.id,
            "name": user.full_name or user.first_name or "User",
            "username": user.username or "",
            "joined_at": iso_now(),
        }
    else:
        db["users"][key]["name"] = user.full_name or user.first_name or db["users"][key].get("name", "User")
        db["users"][key]["username"] = user.username or db["users"][key].get("username", "")
    return db["users"][key]


def user_record_id(user_id):
    key = str(user_id)
    if key not in db["users"]:
        db["users"][key] = {"id": int(user_id), "name": "User", "username": "", "joined_at": iso_now()}
    return db["users"][key]


def package(kind, pid):
    key = {"auto": "autolike_packages", "glory": "glory_packages", "purchase": "purchase_packages"}[kind]
    return next((x for x in db["config"].get(key, []) if str(x.get("id")) == str(pid)), None)


def active_packages(kind):
    key = {"auto": "autolike_packages", "glory": "glory_packages", "purchase": "purchase_packages"}[kind]
    return [x for x in db["config"].get(key, []) if x.get("active", True)]


def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("❤️ Autolikes"), KeyboardButton("🏆 Guild Glory Bot")],
        [KeyboardButton("🛒 Purchase ID"), KeyboardButton("📦 My Orders")],
        [KeyboardButton("❓ Help & Support")],
    ], resize_keyboard=True, is_persistent=True, input_field_placeholder="Choose an option…")


def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])


def back_cancel_kb(back="home"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=back), InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])


def package_kb(kind):
    rows = []
    for p in active_packages(kind):
        rows.append([InlineKeyboardButton(str(p.get("name", "Package")), callback_data=f"pkg_{kind}_{p['id']}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def region_kb(kind):
    rows = []
    for i in range(0, len(REGIONS), 3):
        rows.append([InlineKeyboardButton(label, callback_data=f"region_{kind}_{code}") for label, code in REGIONS[i:i+3]])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=f"packages_{kind}"), InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def summary_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data="confirm")],
        [InlineKeyboardButton("⬅️ Back", callback_data="summary_back"), InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])


def payment_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 I Have Paid", callback_data="paid")],
        [InlineKeyboardButton("📹 How To Pay", callback_data="howto")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])


def contact_admin_kb():
    username = str(db["config"].get("admin_contact", "@nrzravi")).lstrip("@")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{username}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="home")],
    ])


def admin_panel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 Pending Orders", callback_data="admin_pending")],
        [InlineKeyboardButton("📦 Active Orders", callback_data="admin_active")],
        [InlineKeyboardButton("❤️ Autolike Packages", callback_data="admin_pkgs_auto")],
        [InlineKeyboardButton("🏆 Glory Packages", callback_data="admin_pkgs_glory")],
        [InlineKeyboardButton("🛒 Purchase ID Packages", callback_data="admin_pkgs_purchase")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")],
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("⬅️ User Menu", callback_data="home")],
    ])


def admin_order_kb(order_id, kind):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{order_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order_id}")],
        [InlineKeyboardButton("⚙️ Manage", callback_data=f"manage_{order_id}")],
        [InlineKeyboardButton("⬅️ Pending", callback_data="admin_pending")],
    ])


def payment_uri(amount):
    return "upi://pay?" + urlencode({
        "pa": db["config"].get("upi_id", "sandeepshoww@oksbi"),
        "pn": db["config"].get("upi_name", "NRZ RAVI"),
        "am": f"{float(amount):.2f}",
        "cu": "INR",
    })


def make_qr(amount):
    qr = qrcode.QRCode(version=None, box_size=9, border=4)
    qr.add_data(payment_uri(amount))
    qr.make(fit=True)
    img = qr.make_image()
    bio = BytesIO()
    bio.name = "upi_payment_qr.png"
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


def payment_text(order):
    return (
        "🇮🇳 <b>UPI Payment</b>\n\n"
        f"Order ID: <code>{order['id']}</code>\n"
        f"Amount: <b>₹{money(order['amount'])}</b>\n\n"
        f"📲 UPI ID: <code>{escape(str(db['config'].get('upi_id')))}</code>\n"
        f"👤 Name: <b>{escape(str(db['config'].get('upi_name')))}</b>\n\n"
        "⚠️ Pay the exact amount and click <b>I Have Paid</b>."
    )


def order_summary(s):
    kind = s["kind"]
    title = {"auto": "❤️ Autolikes", "glory": "🏆 Guild Glory Bot", "purchase": "🛒 Purchase ID"}[kind]
    p = s["package"]
    lines = [
        "🧾 <b>Order Summary</b>",
        "",
        f"Service: <b>{escape(title)}</b>",
        f"Package: <b>{escape(str(p.get('name','Package')))}</b>",
    ]
    if kind != "purchase":
        lines += [
            f"UID: <code>{escape(s['uid'])}</code>",
            f"Region: <b>{escape(REGION_NAMES.get(s['region'], s['region']))}</b>",
            f"Duration: <b>{int(p.get('days', 1))} day(s)</b>",
        ]
        if kind == "auto":
            lines.append(f"Daily Likes: <b>{int(p.get('likes', 0))}</b>")
    else:
        if p.get("description"):
            lines += ["", f"📝 {escape(str(p['description']))}"]
    lines += ["", f"💰 Price: <b>₹{money(p.get('price', 0))}</b>", "", "Confirm?"]
    return "\n".join(lines)


def admin_order_text(o):
    kind_title = {"auto": "❤️ AutoLikes", "glory": "🏆 Guild Glory Bot", "purchase": "🛒 Purchase ID"}.get(o["kind"], o["kind"])
    text = (
        f"💳 <b>New Payment — {kind_title}</b>\n\n"
        f"Order ID: <code>{o['id']}</code>\n"
        f"User: {escape(o.get('name','User'))} (@{escape(o.get('username') or 'no_username')})\n"
        f"User ID: <code>{o['user_id']}</code>\n"
        f"Package: {escape(o.get('package_name',''))}\n"
        f"Amount: <b>₹{money(o['amount'])}</b>\n"
    )
    if o["kind"] != "purchase":
        text += f"UID: <code>{escape(o.get('uid',''))}</code>\nRegion: <b>{escape(REGION_NAMES.get(o.get('region',''), o.get('region','')))}</b>\n"
        if o["kind"] == "auto":
            text += f"Likes/day: <b>{o.get('likes',0)}</b>\n"
        text += f"Duration: <b>{o.get('days',1)} day(s)</b>\n"
    else:
        if o.get("description"):
            text += f"Description: {escape(o['description'])}\n"
    text += f"UTR: <code>{escape(o.get('utr',''))}</code>\nStatus: <b>{o.get('status')}</b>\nCreated: {o.get('created_at')}"
    return text


def active_order_text(o):
    kind = {"auto": "❤️ Autolikes", "glory": "🏆 Guild Glory Bot", "purchase": "🛒 Purchase ID"}[o["kind"]]
    if o["kind"] == "purchase":
        return f"🛒 <b>{kind}</b>\nPackage: <b>{escape(o['package_name'])}</b>\nStatus: <b>{o['status'].title()}</b>\nOrder ID: <code>{o['id']}</code>"
    return (
        f"{kind}\nPackage: <b>{escape(o['package_name'])}</b>\n"
        f"UID: <code>{o['uid']}</code>\nRegion: {REGION_NAMES.get(o['region'], o['region'])}\n"
        f"Status: <b>{o['status'].title()}</b>\n"
        f"Start: <b>{o.get('start_date','N/A')}</b>\n"
        f"Expiry: <b>{o.get('expiry_date','N/A')}</b>\n"
        + (f"Daily likes: <b>{o.get('likes',0)}</b> at <b>{db['config'].get('daily_run_time','4:00 AM IST')}</b>" if o['kind']=='auto' else f"Daily run: <b>{db['config'].get('daily_run_time','4:00 AM IST')}</b>")
    )


# ============================================================
# COMMON
# ============================================================
async def delete(bot, chat_id, message_id):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def edit_or_reply(q, text, markup=None):
    try:
        await q.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await q.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def notify(context, user_id, text, markup=None):
    try:
        await context.bot.send_message(user_id, text=text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print("notify error", e)


async def send_admins(context, text, markup=None, photo_id=None):
    for aid in OWNER_IDS:
        try:
            if photo_id:
                await context.bot.send_photo(aid, photo=photo_id, caption=text, reply_markup=markup, parse_mode="HTML")
            else:
                await context.bot.send_message(aid, text=text, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            print("admin notify error", e)


# ============================================================
# USER FLOW
# ============================================================
async def home_message(message):
    await message.reply_text(
        "👋 <b>Welcome to the Shop Bot</b>\n\nChoose an option below:",
        reply_markup=main_kb(), parse_mode="HTML"
    )


async def cmd_start(update, context):
    user_record(update.effective_user)
    save_db()
    await home_message(update.message)


async def show_kind(query, context, kind):
    context.user_data.clear()
    context.user_data["flow"] = "select_package"
    context.user_data["kind"] = kind
    title = {"auto": "❤️ Autolikes", "glory": "🏆 Guild Glory Bot", "purchase": "🛒 Purchase ID"}[kind]
    await edit_or_reply(query, f"📅 <b>Select Your {'Duration ' if kind != 'purchase' else ''}Plan:</b>\n\n{escape(title)}", package_kb(kind))


async def show_my_orders(query, user_id):
    orders = [o for o in db["orders"] if int(o.get("user_id", 0)) == int(user_id) and o.get("status") in ("approved", "delivering")]
    if not orders:
        await edit_or_reply(query, "📦 <b>My Orders</b>\n\nNo active approved orders.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="home")]]))
        return
    rows = []
    for o in orders[-20:]:
        title = {"auto": "❤️", "glory": "🏆", "purchase": "🛒"}[o["kind"]]
        rows.append([InlineKeyboardButton(f"{title} {o['package_name'][:35]}", callback_data=f"view_order_{o['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="home")])
    await edit_or_reply(query, "📦 <b>My Orders</b>\n\nSelect an approved order:", InlineKeyboardMarkup(rows))


async def send_payment(query, context):
    s = context.user_data
    p = s["package"]
    order_id = uuid.uuid4().hex[:10].upper()
    order = {
        "id": order_id,
        "user_id": query.from_user.id,
        "name": query.from_user.full_name or query.from_user.first_name or "User",
        "username": query.from_user.username or "",
        "kind": s["kind"],
        "package_id": p["id"],
        "package_name": p.get("name", "Package"),
        "description": p.get("description", ""),
        "amount": float(p.get("price", 0)),
        "status": "verifying_wait",
        "created_at": iso_now(),
    }
    if s["kind"] != "purchase":
        order.update({"uid": s["uid"], "region": s["region"], "days": int(p.get("days",1)), "likes": int(p.get("likes",0))})
    db["orders"].append(order)
    db["stats"]["total_orders"] = int(db["stats"].get("total_orders", 0)) + 1
    save_db()
    context.user_data.clear()
    try:
        msg = await query.message.reply_photo(photo=make_qr(order["amount"]), caption=payment_text(order), parse_mode="HTML", reply_markup=payment_kb())
        order["payment_message_id"] = msg.message_id
        order["payment_chat_id"] = query.message.chat_id
        save_db()
        await delete(context.bot, query.message.chat_id, query.message.message_id)
    except Exception:
        await edit_or_reply(query, payment_text(order), payment_kb())
    return order


VERIFY_MESSAGES = [
    ("⏳ <b>Auto-verifying payment details...</b>", 3),
    ("🔄 <b>Processing payment verification...</b>", 5),
    ("🔎 <b>Verification in process...</b>", 5),
    ("⏱️ <b>Checking transaction details...</b>", 8),
    ("⌛ <b>It may take up to 10 minutes...</b>", 8),
    ("🔐 <b>Securely checking UTR and payment...</b>", 8),
    ("📡 <b>Waiting for payment confirmation...</b>", 8),
    ("🧾 <b>Cross-checking transaction record...</b>", 8),
]


async def verification_loop(context, order_id):
    started = asyncio.get_running_loop().time()
    i = 0
    while asyncio.get_running_loop().time() - started < 600:
        o = next((x for x in db["orders"] if x["id"] == order_id), None)
        if not o or o.get("status") != "verifying":
            return
        text, delay = VERIFY_MESSAGES[i % len(VERIFY_MESSAGES)]
        try:
            await context.bot.edit_message_text(
                chat_id=o["verification_chat_id"], message_id=o["verification_message_id"],
                text=text, parse_mode="HTML"
            )
        except Exception:
            pass
        await asyncio.sleep(delay)
        i += 1
    o = next((x for x in db["orders"] if x["id"] == order_id), None)
    if not o or o.get("status") != "verifying":
        return
    o["status"] = "manual_review"
    o["auto_verify_failed_at"] = iso_now()
    save_db()
    try:
        await context.bot.edit_message_text(
            chat_id=o["verification_chat_id"], message_id=o["verification_message_id"],
            text="⚠️ <b>Auto-verify failed.</b> Sent to admin for manual check. You will be notified!",
            reply_markup=contact_admin_kb(), parse_mode="HTML"
        )
    except Exception:
        pass


# ============================================================
# CALLBACK ROUTER
# ============================================================
async def callback_handler(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data or ""

    if data == "home" or data == "cancel":
        context.user_data.clear()
        try:
            await delete(context.bot, q.message.chat_id, q.message.message_id)
        except Exception:
            pass
        await context.bot.send_message(q.message.chat_id, "👋 <b>Welcome to the Shop Bot</b>\n\nChoose an option below:", reply_markup=main_kb(), parse_mode="HTML")
        return

    if data == "howto":
        url = db["config"].get("how_to_pay_url", "")
        if url:
            await edit_or_reply(q, "📹 <b>How To Pay</b>", InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Open Tutorial", url=url)],
                [InlineKeyboardButton("⬅️ Back", callback_data="payment_back")]
            ]))
        else:
            await q.answer("How-to-pay link is not set by admin.", show_alert=True)
        return

    if data == "payment_back":
        await q.answer("Please start the payment step again.", show_alert=True)
        return

    if data.startswith("packages_"):
        await show_kind(q, context, data.split("_",1)[1])
        return

    if data.startswith("pkg_"):
        _, kind, pid = data.split("_", 2)
        p = package(kind, pid)
        if not p or not p.get("active", True):
            await q.answer("Package unavailable.", show_alert=True); return
        context.user_data.update({"kind": kind, "package": p})
        if kind == "purchase":
            text = f"🛒 <b>{escape(p.get('name','Purchase'))}</b>\n\n"
            if p.get("description"): text += f"📝 {escape(p['description'])}\n\n"
            text += f"💰 Price: <b>₹{money(p.get('price',0))}</b>\n\nBuy this package?"
            await edit_or_reply(q, text, InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Buy", callback_data="purchase_buy")],
                [InlineKeyboardButton("⬅️ Back", callback_data="packages_purchase"), InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]))
        else:
            context.user_data["flow"] = "region"
            await edit_or_reply(q, "🌍 <b>Select Your Region:</b>", region_kb(kind))
        return

    if data.startswith("region_"):
        _, kind, region = data.split("_", 2)
        context.user_data.update({"kind": kind, "region": region, "flow": "uid"})
        await edit_or_reply(q, "📱 <b>Please enter the UID (Player ID):</b>", cancel_kb())
        return

    if data == "summary_back":
        kind = context.user_data.get("kind")
        if kind:
            await edit_or_reply(q, "🌍 <b>Select Your Region:</b>", region_kb(kind))
        return

    if data == "confirm":
        if context.user_data.get("flow") != "confirm":
            await q.answer("Order session expired. Start again.", show_alert=True); return
        await send_payment(q, context)
        return

    if data == "purchase_buy":
        if context.user_data.get("kind") != "purchase" or not context.user_data.get("package"):
            await q.answer("Order session expired.", show_alert=True); return
        await send_payment(q, context)
        return

    if data == "paid":
        # Delete the payment message and ask for screenshot.
        order = next((o for o in db["orders"] if o.get("payment_message_id") == q.message.message_id and o.get("user_id") == uid and o.get("status") == "verifying_wait"), None)
        if not order:
            await q.answer("Payment session expired. Start again.", show_alert=True); return
        order["status"] = "awaiting_screenshot"
        save_db()
        await delete(context.bot, q.message.chat_id, q.message.message_id)
        msg = await context.bot.send_message(uid, "📸 <b>Send screenshot of your payment:</b>\n\nPlease send the payment screenshot here.", reply_markup=cancel_kb(), parse_mode="HTML")
        context.user_data.clear()
        context.user_data["flow"] = "payment_photo"
        context.user_data["order_id"] = order["id"]
        context.user_data["prompt_message_id"] = msg.message_id
        return

    if data.startswith("view_order_"):
        oid = data[len("view_order_"):]
        o = next((x for x in db["orders"] if x["id"] == oid and int(x.get("user_id",0)) == uid), None)
        if not o:
            await q.answer("Order not found.", show_alert=True); return
        await edit_or_reply(q, active_order_text(o), InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ My Orders", callback_data="my_orders")]]))
        return

    if data == "my_orders":
        await show_my_orders(q, uid); return

    if data == "admin_panel":
        if not is_owner(uid): return
        await edit_or_reply(q, "🔐 <b>Admin Panel</b>\n\nChoose what you want to manage:", admin_panel_kb()); return

    if data.startswith("admin_") or data.startswith("approve_") or data.startswith("reject_") or data.startswith("manage_") or data.startswith("sendfile_") or data.startswith("complete_"):
        if not is_owner(uid):
            await q.answer("Admin only.", show_alert=True); return
        await admin_callback(q, context, data); return


# ============================================================
# MESSAGE HANDLER
# ============================================================
async def msg_handler(update, context):
    user_record(update.effective_user)
    flow = context.user_data.get("flow")

    if update.message.photo and flow == "payment_photo":
        oid = context.user_data.get("order_id")
        o = next((x for x in db["orders"] if x["id"] == oid and int(x["user_id"]) == update.effective_user.id), None)
        if not o:
            context.user_data.clear(); return
        o["photo_id"] = update.message.photo[-1].file_id
        o["status"] = "awaiting_utr"
        save_db()
        context.user_data["flow"] = "payment_utr"
        await update.message.reply_text("🔢 <b>Enter UTR / Transaction ID (Numbers & Letters Allowed):</b>", reply_markup=cancel_kb(), parse_mode="HTML")
        return

    if not update.message.text:
        # Admin can send a file after approving a Purchase ID order.
        if is_owner(update.effective_user.id) and flow == "admin_purchase_file":
            oid = context.user_data.get("admin_order_id")
            o = next((x for x in db["orders"] if x["id"] == oid), None)
            if not o:
                context.user_data.clear(); return
            if update.message.document:
                o["file_type"] = "document"; o["file_id"] = update.message.document.file_id
            elif update.message.video:
                o["file_type"] = "video"; o["file_id"] = update.message.video.file_id
            elif update.message.photo:
                o["file_type"] = "photo"; o["file_id"] = update.message.photo[-1].file_id
            elif update.message.animation:
                o["file_type"] = "animation"; o["file_id"] = update.message.animation.file_id
            else:
                return
            o["status"] = "completed"
            o["file_sent_at"] = iso_now()
            o["completed_at"] = iso_now()
            save_db()
            await send_order_file(context, o)
            context.user_data.clear()
            await update.message.reply_text("✅ File sent to the user. Order is now complete.", reply_markup=admin_back_kb())
            return
        return

    text = update.message.text.strip()

    # Bottom menu buttons always start a fresh flow.
    menu = {
        "❤️ Autolikes": "auto", "🏆 Guild Glory Bot": "glory", "🛒 Purchase ID": "purchase",
    }
    if text in menu:
        await show_kind_from_message(update.message, context, menu[text]); return
    if text == "📦 My Orders":
        await send_my_orders_message(update.message, update.effective_user.id); return
    if text == "❓ Help & Support":
        await update.message.reply_text(db["config"].get("help_text", DEFAULT_CONFIG["help_text"]), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📹 How To Use (Video)", url=db["config"].get("how_to_pay_url"))] if db["config"].get("how_to_pay_url") else [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{str(db['config'].get('admin_contact','@nrzravi')).lstrip('@')}")],
            [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{str(db['config'].get('admin_contact','@nrzravi')).lstrip('@')}")],
        ]), parse_mode="HTML")
        return

    if flow == "uid":
        if not uid_ok(text):
            await update.message.reply_text("❌ Invalid UID. Please enter a numeric UID (6–15 digits).", parse_mode="HTML"); return
        context.user_data["uid"] = text
        context.user_data["flow"] = "confirm"
        await update.message.reply_text(order_summary(context.user_data), reply_markup=summary_kb(), parse_mode="HTML")
        return

    if flow == "payment_utr":
        if not utr_ok(text):
            await update.message.reply_text("❌ Invalid UTR. Use 6–40 letters/numbers only.", parse_mode="HTML"); return
        oid = context.user_data.get("order_id")
        o = next((x for x in db["orders"] if x["id"] == oid and int(x["user_id"]) == update.effective_user.id), None)
        if not o:
            context.user_data.clear(); await update.message.reply_text("❌ Order not found."); return
        o["utr"] = text
        o["status"] = "verifying"
        o["verification_chat_id"] = update.effective_chat.id
        save_db()
        context.user_data.clear()
        wait = await update.message.reply_text("⏳ <b>Auto-verifying payment details...</b>", parse_mode="HTML")
        o["verification_message_id"] = wait.message_id
        save_db()
        await send_admins(context, admin_order_text(o), admin_order_kb(o["id"], o["kind"]), o.get("photo_id"))
        asyncio.create_task(verification_loop(context, o["id"]))
        return

    if is_owner(update.effective_user.id) and flow and flow.startswith("admin_"):
        await handle_admin_text(update, context, text)


async def show_kind_from_message(message, context, kind):
    context.user_data.clear()
    context.user_data.update({"flow": "select_package", "kind": kind})
    title = {"auto": "❤️ Autolikes", "glory": "🏆 Guild Glory Bot", "purchase": "🛒 Purchase ID"}[kind]
    await message.reply_text(f"📅 <b>Select Your Plan:</b>\n\n{title}", reply_markup=package_kb(kind), parse_mode="HTML")


async def send_my_orders_message(message, user_id):
    orders = [o for o in db["orders"] if int(o.get("user_id",0)) == int(user_id) and o.get("status") in ("approved", "delivering")]
    if not orders:
        await message.reply_text("📦 <b>My Orders</b>\n\nNo active approved orders.", reply_markup=main_kb(), parse_mode="HTML"); return
    for o in orders[-20:]:
        await message.reply_text(active_order_text(o), parse_mode="HTML")


# ============================================================
# ADMIN
# ============================================================
def admin_back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel")]])


def admin_pkg_list_kb(kind):
    rows=[]
    for p in db["config"].get({"auto":"autolike_packages","glory":"glory_packages","purchase":"purchase_packages"}[kind],[]):
        st="🟢" if p.get("active",True) else "🔴"
        rows.append([InlineKeyboardButton(f"{st} {p.get('name','Package')}", callback_data=f"admin_pkgview_{kind}_{p['id']}")])
    rows.append([InlineKeyboardButton("➕ Add Package", callback_data=f"admin_pkgadd_{kind}")])
    rows.append([InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)


async def admin_callback(q, context, data):
    if data == "admin_pending":
        pending=[o for o in db["orders"] if o.get("status") in ("verifying","manual_review")]
        if not pending:
            await edit_or_reply(q,"🧾 <b>Pending Orders</b>\n\nNo pending orders.",admin_back_kb()); return
        o=pending[0]
        await edit_or_reply(q,admin_order_text(o),admin_order_kb(o["id"],o["kind"])); return

    if data == "admin_active":
        active=[o for o in db["orders"] if o.get("status") in ("approved","delivering")]
        if not active:
            await edit_or_reply(q,"📦 <b>Active Orders</b>\n\nNone.",admin_back_kb()); return
        text="📦 <b>Active Orders</b>\n\n"+"\n\n".join(active_order_text(o) for o in active[-20:])
        await edit_or_reply(q,text,admin_back_kb()); return

    if data.startswith("approve_"):
        oid=data[len("approve_"):]
        o=next((x for x in db["orders"] if x["id"]==oid),None)
        if not o or o.get("status") not in ("verifying","manual_review"):
            await q.answer("Order is no longer pending.",show_alert=True); return
        o["status"]="approved"; o["approved_at"]=iso_now()
        if o["kind"] in ("auto","glory"):
            start=now_ist().date(); expiry=start+timedelta(days=int(o.get("days",1)))
            o["start_date"]=start.strftime("%Y-%m-%d"); o["expiry_date"]=expiry.strftime("%Y-%m-%d")
        save_db()
        if o["kind"]=="purchase":
            await notify(context,o["user_id"],f"✅ <b>Order Received</b>\n\nOrder ID: <code>{oid}</code>\nPackage: <b>{escape(o['package_name'])}</b>\n\nAdmin has approved your payment. Your file will be sent shortly.",None)
            await edit_or_reply(q,"✅ <b>Payment approved.</b>\n\nNow send the file for this Purchase ID order.",InlineKeyboardMarkup([[InlineKeyboardButton("📤 Send File",callback_data=f"sendfile_{oid}")],[InlineKeyboardButton("⬅️ Admin Panel",callback_data="admin_panel")]]))
        else:
            text=("✅ <b>Order Received</b>\n\n"
                  f"Order ID: <code>{oid}</code>\nService: <b>{escape(o['package_name'])}</b>\n"
                  f"UID: <code>{o['uid']}</code>\nRegion: {REGION_NAMES.get(o['region'],o['region'])}\n"
                  f"Daily run: <b>{db['config'].get('daily_run_time','4:00 AM IST')}</b>\n"
                  f"Duration: <b>{o['days']} day(s)</b>\nExpiry: <b>{o['expiry_date']}</b>")
            if o["kind"]=="auto": text += f"\nDaily Likes: <b>{o.get('likes',0)}</b>"
            await notify(context,o["user_id"],text,InlineKeyboardMarkup([[InlineKeyboardButton("📦 My Orders",callback_data="my_orders")]]))
            await edit_or_reply(q,"✅ Order approved. User has been notified.\n\n"+admin_order_text(o),admin_back_kb())
        return

    if data.startswith("reject_"):
        oid=data[len("reject_"):]
        o=next((x for x in db["orders"] if x["id"]==oid),None)
        if not o or o.get("status") not in ("verifying","manual_review"):
            await q.answer("Order is no longer pending.",show_alert=True); return
        context.user_data["flow"]="admin_reject_reason"; context.user_data["admin_order_id"]=oid
        await edit_or_reply(q,"❌ <b>Reject Order</b>\n\nSend the rejection reason, for example:\n<code>Fake payment / Invalid UTR</code>",admin_back_kb()); return

    if data.startswith("manage_"):
        oid=data[len("manage_"):]
        o=next((x for x in db["orders"] if x["id"]==oid),None)
        if not o: await q.answer("Order not found.",show_alert=True); return
        await edit_or_reply(q,admin_order_text(o),InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Mark Completed",callback_data=f"complete_{oid}")],
            [InlineKeyboardButton("🗑 Remove Order",callback_data=f"remove_{oid}")],
            [InlineKeyboardButton("⬅️ Admin Panel",callback_data="admin_panel")]
        ])); return

    if data.startswith("complete_"):
        oid=data[len("complete_"):]
        o=next((x for x in db["orders"] if x["id"]==oid),None)
        if o:
            o["status"]="completed"; o["completed_at"]=iso_now(); save_db()
            await notify(context,o["user_id"],f"✅ <b>Order Completed</b>\n\nOrder <code>{oid}</code> has been completed.")
        await edit_or_reply(q,"✅ Order marked completed.",admin_back_kb()); return

    if data.startswith("remove_"):
        oid=data[len("remove_"):]
        db["orders"]=[o for o in db["orders"] if o["id"]!=oid]; save_db()
        await edit_or_reply(q,"🗑 Order removed.",admin_back_kb()); return

    if data.startswith("sendfile_"):
        oid=data[len("sendfile_"):]
        o=next((x for x in db["orders"] if x["id"]==oid),None)
        if not o or o["kind"]!="purchase" or o.get("status")!="approved":
            await q.answer("Purchase order is not ready.",show_alert=True); return
        context.user_data["flow"]="admin_purchase_file"; context.user_data["admin_order_id"]=oid
        await edit_or_reply(q,"📤 <b>Send File</b>\n\nNow send the document, video, photo or animation that should be delivered to the user.",admin_back_kb()); return

    if data.startswith("admin_pkgs_"):
        kind=data[len("admin_pkgs_"):]
        title={"auto":"❤️ Autolike Packages","glory":"🏆 Glory Packages","purchase":"🛒 Purchase ID Packages"}.get(kind,kind)
        await edit_or_reply(q,f"⚙️ <b>{title}</b>\n\nSelect a package to edit or add a new one.",admin_pkg_list_kb(kind)); return

    if data.startswith("admin_pkgview_"):
        _,_,kind,pid=data.split("_",3)
        p=package(kind,pid)
        if not p: await q.answer("Package not found.",show_alert=True); return
        extra=""
        if kind=="auto": extra=f"\nLikes/day: {p.get('likes',0)}\nDays: {p.get('days',1)}"
        elif kind=="glory": extra=f"\nDays: {p.get('days',1)}"
        else: extra=f"\nDescription: {escape(p.get('description',''))}"
        st="🟢 Active" if p.get('active',True) else "🔴 Inactive"
        await edit_or_reply(q,f"📦 <b>{escape(p.get('name','Package'))}</b>\n\nStatus: {st}\nPrice: ₹{money(p.get('price',0))}{extra}",InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Edit Name",callback_data=f"admin_editname_{kind}_{pid}"),InlineKeyboardButton("💰 Edit Price",callback_data=f"admin_editprice_{kind}_{pid}")],
            ([InlineKeyboardButton("❤️ Edit Likes",callback_data=f"admin_editlikes_{pid}")] if kind=="auto" else []),
            ([InlineKeyboardButton("📅 Edit Days",callback_data=f"admin_editdays_{kind}_{pid}")] if kind in ("auto","glory") else [InlineKeyboardButton("📝 Edit Description",callback_data=f"admin_editdesc_{pid}")]),
            [InlineKeyboardButton("🔄 Toggle Status",callback_data=f"admin_toggle_{kind}_{pid}"),InlineKeyboardButton("🗑 Delete",callback_data=f"admin_delete_{kind}_{pid}")],
            [InlineKeyboardButton("⬅️ Back",callback_data=f"admin_pkgs_{kind}")]
        ])); return

    if data.startswith("admin_pkgadd_"):
        kind=data[len("admin_pkgadd_"):]
        context.user_data.update({"flow":"admin_add_pkg","admin_kind":kind})
        prompt = "Name | Price | Days | Likes" if kind=="auto" else ("Name | Price | Days" if kind=="glory" else "Name | Price | Description")
        await edit_or_reply(q,f"➕ <b>Add Package</b>\n\nSend exactly:\n<code>{prompt}</code>",admin_back_kb()); return

    for prefix, flow, field in [
        ("admin_editname_","admin_edit_pkg_name","name"),
        ("admin_editprice_","admin_edit_pkg_price","price"),
        ("admin_editdays_","admin_edit_pkg_days","days"),
        ("admin_editlikes_","admin_edit_pkg_likes","likes"),
        ("admin_editdesc_","admin_edit_pkg_desc","description"),
    ]:
        if data.startswith(prefix):
            raw=data[len(prefix):]
            parts=raw.split("_")
            if field=="likes": kind="auto"; pid=parts[0]
            else: kind=parts[0]; pid=parts[1] if len(parts)>1 else ""
            context.user_data.update({"flow":flow,"admin_kind":kind,"admin_pkg_id":pid})
            await edit_or_reply(q,{"name":"✏️ Send new package name:","price":"💰 Send new price:","days":"📅 Send new duration in days:","likes":"❤️ Send new likes/day:","description":"📝 Send new description:"}[field],admin_back_kb()); return

    if data.startswith("admin_toggle_"):
        _,_,kind,pid=data.split("_",3); p=package(kind,pid)
        if p: p["active"]=not p.get("active",True); save_db()
        await edit_or_reply(q,"✅ Package status updated.",InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back",callback_data=f"admin_pkgview_{kind}_{pid}")]])); return

    if data.startswith("admin_delete_"):
        _,_,kind,pid=data.split("_",3)
        key={"auto":"autolike_packages","glory":"glory_packages","purchase":"purchase_packages"}[kind]
        db["config"][key]=[p for p in db["config"].get(key,[]) if str(p.get("id"))!=pid]; save_db()
        await edit_or_reply(q,"🗑 Package deleted.",InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Packages",callback_data=f"admin_pkgs_{kind}")]])); return

    if data == "admin_settings":
        await edit_or_reply(q,"⚙️ <b>Settings</b>\n\nChoose what to edit:",InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 UPI / Payment Details",callback_data="admin_set_upi")],
            [InlineKeyboardButton("👤 Admin Contact",callback_data="admin_set_contact")],
            [InlineKeyboardButton("📹 How To Pay / Help Video",callback_data="admin_set_howto")],
            [InlineKeyboardButton("❓ Help Text",callback_data="admin_set_help")],
            [InlineKeyboardButton("⏰ Daily Run Time",callback_data="admin_set_time")],
            [InlineKeyboardButton("⬅️ Admin Panel",callback_data="admin_panel")]
        ])); return

    for key, prompt in [
        ("admin_set_upi","💳 Send: <code>UPI_ID | NAME</code>"),
        ("admin_set_contact","👤 Send admin username, e.g. <code>@nrzravi</code>"),
        ("admin_set_howto","📹 Send a public https:// tutorial URL (or send - to clear)."),
        ("admin_set_help","❓ Send the complete Help & Support text. HTML is supported."),
        ("admin_set_time","⏰ Send daily run time, e.g. <code>4:00 AM IST</code>"),
    ]:
        if data==key:
            context.user_data["flow"]=key; await edit_or_reply(q,prompt,admin_back_kb()); return

    if data == "admin_users":
        await edit_or_reply(q,f"👥 <b>Users</b>\n\nRegistered users: <b>{len(db['users'])}</b>",admin_back_kb()); return


async def handle_admin_text(update, context, text):
    flow=context.user_data.get("flow")
    if flow=="admin_reject_reason":
        oid=context.user_data.get("admin_order_id"); o=next((x for x in db["orders"] if x["id"]==oid),None)
        if not o: context.user_data.clear(); return
        o["status"]="rejected"; o["rejected_at"]=iso_now(); o["reject_reason"]=text; save_db(); context.user_data.clear()
        await notify(context,o["user_id"],f"❌ <b>Order Rejected</b>\n\nOrder ID: <code>{oid}</code>\nReason: <b>{escape(text)}</b>",contact_admin_kb())
        await update.message.reply_text("❌ Order rejected and user notified.",reply_markup=admin_back_kb()); return

    if flow=="admin_add_pkg":
        kind=context.user_data.get("admin_kind"); parts=[x.strip() for x in text.split("|",2 if kind=="purchase" else 3)]
        try:
            if kind=="auto":
                if len(parts)!=4: raise ValueError
                name,price,days,likes=parts; item={"id":uuid.uuid4().hex[:8],"name":name,"price":float(price),"days":int(days),"likes":int(likes),"active":True}
            elif kind=="glory":
                if len(parts)!=3: raise ValueError
                name,price,days=parts; item={"id":uuid.uuid4().hex[:8],"name":name,"price":float(price),"days":int(days),"active":True}
            else:
                if len(parts)!=3: raise ValueError
                name,price,description=parts; item={"id":uuid.uuid4().hex[:8],"name":name,"price":float(price),"description":description,"active":True}
        except Exception:
            prompt="Name | Price | Days | Likes" if kind=="auto" else ("Name | Price | Days" if kind=="glory" else "Name | Price | Description")
            await update.message.reply_text(f"❌ Invalid format. Use: {prompt}"); return
        key={"auto":"autolike_packages","glory":"glory_packages","purchase":"purchase_packages"}[kind]
        db["config"][key].append(item); save_db(); context.user_data.clear()
        await update.message.reply_text("✅ Package added.",reply_markup=admin_back_kb()); return

    if flow.startswith("admin_edit_pkg_"):
        kind=context.user_data.get("admin_kind"); pid=context.user_data.get("admin_pkg_id"); p=package(kind,pid)
        if not p: context.user_data.clear(); await update.message.reply_text("Package not found."); return
        field={"admin_edit_pkg_name":"name","admin_edit_pkg_price":"price","admin_edit_pkg_days":"days","admin_edit_pkg_likes":"likes","admin_edit_pkg_desc":"description"}[flow]
        try:
            if field=="name" or field=="description": p[field]=text
            elif field=="price": p[field]=float(text.replace("₹",""))
            else: p[field]=int(text)
        except Exception:
            await update.message.reply_text("❌ Invalid value."); return
        save_db(); context.user_data.clear(); await update.message.reply_text("✅ Package updated.",reply_markup=admin_back_kb()); return

    if flow=="admin_set_upi":
        parts=[x.strip() for x in text.split("|",1)]
        if len(parts)!=2: await update.message.reply_text("Use: UPI_ID | NAME"); return
        db["config"]["upi_id"],db["config"]["upi_name"]=parts; save_db(); context.user_data.clear(); await update.message.reply_text("✅ UPI details updated.",reply_markup=admin_back_kb()); return
    if flow=="admin_set_contact":
        db["config"]["admin_contact"]=text.lstrip("@"); save_db(); context.user_data.clear(); await update.message.reply_text("✅ Admin contact updated.",reply_markup=admin_back_kb()); return
    if flow=="admin_set_howto":
        db["config"]["how_to_pay_url"]="" if text=="-" else text; save_db(); context.user_data.clear(); await update.message.reply_text("✅ Tutorial URL updated.",reply_markup=admin_back_kb()); return
    if flow=="admin_set_help":
        db["config"]["help_text"]=text; save_db(); context.user_data.clear(); await update.message.reply_text("✅ Help text updated.",reply_markup=admin_back_kb()); return
    if flow=="admin_set_time":
        db["config"]["daily_run_time"]=text; save_db(); context.user_data.clear(); await update.message.reply_text("✅ Daily run time updated.",reply_markup=admin_back_kb()); return


async def send_order_file(context, o):
    try:
        if o.get("file_type")=="document":
            await context.bot.send_document(o["user_id"],o["file_id"],caption=f"📦 <b>Your Purchase ID order</b>\n\nOrder ID: <code>{o['id']}</code>\nPackage: <b>{escape(o['package_name'])}</b>",parse_mode="HTML")
        elif o.get("file_type")=="video":
            await context.bot.send_video(o["user_id"],o["file_id"],caption=f"📦 <b>Your Purchase ID order</b>\n\nOrder ID: <code>{o['id']}</code>",parse_mode="HTML")
        elif o.get("file_type")=="photo":
            await context.bot.send_photo(o["user_id"],o["file_id"],caption=f"📦 <b>Your Purchase ID order</b>\n\nOrder ID: <code>{o['id']}</code>",parse_mode="HTML")
        elif o.get("file_type")=="animation":
            await context.bot.send_animation(o["user_id"],o["file_id"],caption=f"📦 <b>Your Purchase ID order</b>\n\nOrder ID: <code>{o['id']}</code>",parse_mode="HTML")
    except Exception as e:
        print("send file error",e)


# ============================================================
# COMMANDS / SCHEDULER
# ============================================================
async def cmd_help(update, context):
    await update.message.reply_text(db["config"].get("help_text", DEFAULT_CONFIG["help_text"]), parse_mode="HTML", reply_markup=main_kb())


async def cmd_admin(update, context):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Not available."); return
    await update.message.reply_text("🔐 <b>Admin Panel</b>\n\nChoose what you want to manage:",reply_markup=admin_panel_kb(),parse_mode="HTML")


async def daily_admin_reminder(context=None):
    active=[o for o in db["orders"] if o.get("kind") in ("auto","glory") and o.get("status")=="approved" and o.get("expiry_date")]
    active=[o for o in active if o["expiry_date"] >= now_ist().strftime("%Y-%m-%d")]
    if not active: return
    text="🌅 <b>4:00 AM Order Reminder</b>\n\n"+"\n".join(f"• {o['kind']} | UID {o['uid']} | {o['package_name']} | expires {o['expiry_date']}" for o in active)
    for aid in OWNER_IDS:
        try: await APP.bot.send_message(aid,text=text,parse_mode="HTML")
        except Exception: pass


APP=None
scheduler=AsyncIOScheduler()


async def post_init(application):
    global APP
    APP=application
    await application.bot.set_my_commands([BotCommand("start","Open main menu"),BotCommand("help","Help & Support")],scope=BotCommandScopeDefault())
    for aid in OWNER_IDS:
        try:
            await application.bot.set_my_commands([BotCommand("start","Open main menu"),BotCommand("admin","Open Admin Panel")],scope=BotCommandScopeChat(chat_id=aid))
        except Exception: pass
    scheduler.add_job(daily_admin_reminder,CronTrigger(hour=4,minute=0,timezone=IST),id="daily_order_reminder",replace_existing=True)
    scheduler.start()
    save_db()
    print("Bot online. Payment verification is manual/admin controlled; no external payment API is called.")


def main():
    if not TOKEN: raise RuntimeError("TELEGRAM_TOKEN is not set")
    app=Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",cmd_start))
    app.add_handler(CommandHandler("help",cmd_help))
    app.add_handler(CommandHandler("admin",cmd_admin))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND,msg_handler))
    app.add_handler(MessageHandler((filters.Document.ALL | filters.VIDEO | filters.ANIMATION) & ~filters.COMMAND,msg_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,msg_handler))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__=="__main__":
    main()
