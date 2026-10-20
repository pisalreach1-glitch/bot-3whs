import os
import sys
import json
import math
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import time
from typing import Optional
import pytz
from dotenv import load_dotenv

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from ai_service import AIService
from script_models import (
    PlanResult,
    count_khmer_dialogue_units,
    DEFAULT_CHARS_PER_SECOND,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ai_service = AIService()

# ─────────────────────────────────────────────
# Health Check (Render.com)
# ─────────────────────────────────────────────
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("3WHs Bot Running!".encode("utf-8"))

    def log_message(self, format, *args):
        return

def start_health_check_server():
    port_str = os.getenv("PORT")
    if not port_str:
        return
    try:
        port = int(port_str)
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info(f"Health check server running on port {port}")
    except Exception as e:
        logger.error(f"Health check server error: {e}")

# ─────────────────────────────────────────────
# 6 Viral Content Types Config
# ─────────────────────────────────────────────
CONTENT_TYPES = {
    "3whs": {
        "emoji": "🎬",
        "name": "3WHs Hook Script",
        "description": "Script វីដេអូខ្លីពេញលេញ (Hook→What→Why→How→CTA)",
        "question": (
            "🎬 *3WHs Hook Script (ស្គ្រីបវីដេអូខ្លី)*\n\n"
            "📝 *សូមប្រាប់ពីប្រធានបទ ឬអាជីវកម្មរបស់អ្នក* ដែលចង់ធ្វើ Script៖\n\n"
            "_ឧទាហរណ៍៖_\n"
            "• «លក់សម្លៀកបំពាក់នារី» ឬ «វិធីរើសខោខូវប៊យឱ្យសមរាង»\n"
            "• «បង្រៀនធ្វើម្ហូបខ្មែរ» ឬ «របៀបឆាសាច់គោឱ្យទន់ឆ្ងាញ់»\n"
            "• «អចលនទ្រព្យ» ឬ «គន្លឹះទិញដីធ្លីដំបូងកុំឱ្យចាញ់បោកគេ»\n"
            "• «ហាងកាហ្វេ» ឬ «វិធីឆុងកាហ្វេ Cold Brew ខ្លួនឯង»\n"
            "• «គន្លឹះសន្សំប្រាក់សម្រាប់អ្នកធ្វើការ»"
        ),
    },
    "pov": {
        "emoji": "🎭",
        "name": "POV / Storytelling",
        "description": "រឿងពិត ទាក់អារម្មណ៍ Emotion + Watch Time ខ្ពស់",
        "question": (
            "🎭 *POV / Storytelling (អារម្មណ៍ & រឿងពិត)*\n\n"
            "📝 *សូមប្រាប់ពីស្ថានភាព (POV) ឬរឿងរ៉ាវ* ដែលអ្នកចង់ចែករំលែក៖\n\n"
            "_ឧទាហរណ៍៖_\n"
            "• «POV: ថ្ងៃដំបូងដែលខ្ញុំចាប់ផ្តើមលក់អនឡាញ គ្មានអ្នកទិញសោះ»\n"
            "• «ពេលដែលអតិថិជនសុំតថ្លៃស្ទើរស្មើដើម»\n"
            "• «POV: ថ្ងៃដំបូងចូលរៀនជំនាញថ្មី ទាំងដែលគ្មានមូលដ្ឋាន»\n"
            "• «ពេលដែល Order ដំបូងផ្ទុះឡើង វេចខ្ចប់ដល់យប់ជ្រៅ»\n"
            "• «POV: មិត្តភក្តិគិតថាការងារ Freelance ស្រួលណាស់»"
        ),
    },
    "myth": {
        "emoji": "⚡",
        "name": "Myth vs Reality",
        "description": "បំបែកការយល់ខុស → មនុស្សចូលចិត្ត Comment & Debate",
        "question": (
            "⚡ *Myth vs Reality (កែកំហុសយល់ខុស)*\n\n"
            "📝 *សូមប្រាប់ពីការយល់ច្រឡំ ឬជំនឿខុស* ក្នុងវិស័យរបស់អ្នក៖\n\n"
            "_ឧទាហរណ៍៖_\n"
            "• «លក់អនឡាញទាល់តែមានដើមទុនរាប់ពាន់ដុល្លារទើបធ្វើបាន»\n"
            "• «ធ្វើម្ហូបខ្មែរពិបាក និងចំណាយពេលយូរ»\n"
            "• «ទាល់តែនិយាយពូកែទើបអាចធ្វើ Content វីដេអូបាន»\n"
            "• «ការតមបាយយប់ ជួយឱ្យស្រកទម្ងន់លឿន»\n"
            "• «បើកហាងកាហ្វេស្រួលចំណេញណាស់»"
        ),
    },
    "transform": {
        "emoji": "🔄",
        "name": "Before & After",
        "description": "ការផ្លាស់ប្តូរ & លទ្ធផលជាក់ស្តែង → Save & Share ច្រើន",
        "question": (
            "🔄 *Before & After (ការផ្លាស់ប្តូរជាក់ស្តែង)*\n\n"
            "📝 *សូមប្រាប់ពីការផ្លាស់ប្ដូរ (មុន និង ក្រោយ)* ដែលអ្នកចង់បង្ហាញ៖\n\n"
            "_ឧទាហរណ៍៖_\n"
            "• «មុន និង ក្រោយប្រើផលិតផលថែរក្សាស្បែក ៣០ ថ្ងៃ»\n"
            "• «ពីអ្នកមិនចេះធ្វើម្ហូបសោះ រហូតបើកហាងផ្ទាល់ខ្លួន»\n"
            "• «បន្ទប់ចាស់ទ្រុឌទ្រោម រៀបចំឡើងវិញក្លាយជាស្អាតដូច Mini Studio»\n"
            "• «ពីអ្នកខ្លាចកាមេរ៉ា ក្លាយជា Content Creator រកចំណូលបាន»\n"
            "• «មុន និង ក្រោយរៀបចំផែនការហិរញ្ញវត្ថុ ៦ ខែ»"
        ),
    },
    "hottake": {
        "emoji": "🌶️",
        "name": "Hot Take / Opinion",
        "description": "គំនិតប្លែក ឬផ្ទុយពីគេ → ទាក់ទាញ Comment ផ្ទុះ",
        "question": (
            "🌶️ *Hot Take / Opinion (មតិប្លែក ឬផ្ទុយពីគេ)*\n\n"
            "📝 *សូមប្រាប់ពីមតិផ្ទុយ ឬទស្សនៈប្លែក* របស់អ្នក៖\n\n"
            "_ឧទាហរណ៍៖_\n"
            "• «ការបញ្ចុះតម្លៃមិនមែនជាវិធីលក់ដាច់ល្អបំផុតទេ»\n"
            "• «រៀនជំនាញជាក់ស្តែង មានប្រយោជន៍ជាងសញ្ញាបត្រមួយចំនួន»\n"
            "• «ធ្វើ Content ច្រើន មិនស្មើនឹងធ្វើ Content ត្រូវចិត្តមនុស្សទេ»\n"
            "• «មិនចាំបាច់មានទូរស័ព្ទថ្លៃ ទើបអាចថតវីដេអូស្អាតបាននោះឡើយ»"
        ),
    },
    "toplist": {
        "emoji": "📋",
        "name": "Top List / Ranking",
        "description": "បញ្ជី Top 3, 5, 7 ចំណុចសំខាន់ៗ → ងាយ Save ទុក",
        "question": (
            "📋 *Top List / Ranking (បញ្ជី Top)*\n\n"
            "📝 *តើអ្នកចង់ធ្វើ Top ប៉ុន្មាន និងលើប្រធានបទអ្វី?*\n\n"
            "_ឧទាហរណ៍៖_\n"
            "• «Top 5 កំហុសដែលអ្នកលក់អនឡាញថ្មីៗតែងជួប»\n"
            "• «Top 3 មុខម្ហូបខ្មែរងាយស្រួលធ្វើ និងចំណាយតិចបំផុត»\n"
            "• «Top 4 App ជួយកាត់តវីដេអូលើទូរស័ព្ទដោយឥតគិតថ្លៃ»\n"
            "• «Top 5 វិធីសន្សំប្រាក់ឱ្យសល់ច្រើនក្នុងមួយខែ»\n"
            "• «Top 3 សៀវភៅដែលអ្នករកស៊ីគួរតែអាន»"
        ),
    },
}

DEFAULT_DURATION = "60 វិនាទី"
DEFAULT_DAILY_TIME = "08:00"

# ─────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────
SUBSCRIBERS_FILE = "subscribers.json"
USER_SETTINGS_FILE = "user_settings.json"

def load_user_settings() -> dict:
    if os.path.exists(USER_SETTINGS_FILE):
        try:
            with open(USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load user settings: {e}")
    return {}

def save_user_settings_to_file(settings: dict):
    try:
        with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save user settings: {e}")

user_settings = load_user_settings()

def get_user_duration(chat_id: int) -> str:
    cfg = user_settings.get(str(chat_id), {})
    return cfg.get("duration", DEFAULT_DURATION)

def set_user_duration(chat_id: int, duration: str):
    str_id = str(chat_id)
    if str_id not in user_settings:
        user_settings[str_id] = {}
    user_settings[str_id]["duration"] = duration
    save_user_settings_to_file(user_settings)

def get_user_pace(chat_id: int) -> float:
    cfg = user_settings.get(str(chat_id), {})
    return float(cfg.get("pace", DEFAULT_CHARS_PER_SECOND))

def set_user_pace(chat_id: int, pace: float):
    str_id = str(chat_id)
    if str_id not in user_settings:
        user_settings[str_id] = {}
    user_settings[str_id]["pace"] = round(pace, 2)
    save_user_settings_to_file(user_settings)

def load_subscribers() -> set:
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f).get("subscribers", []))
        except Exception as e:
            logger.error(f"Failed to load subscribers: {e}")
    return set()

def save_subscribers(subs: set):
    try:
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"subscribers": list(subs)}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save subscribers: {e}")

subscribers = load_subscribers()

# ─────────────────────────────────────────────
# Helpers & Message Utilities
# ─────────────────────────────────────────────
def split_message(text: str, max_length: int = 4000) -> list[str]:
    if len(text) <= max_length:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
        idx = text.rfind("\n", 0, max_length)
        if idx == -1:
            idx = max_length
        chunks.append(text[:idx])
        text = text[idx:].lstrip()
    return chunks

async def safe_reply(target, text: str, reply_markup=None):
    chunks = split_message(text)
    msg_target = target.message if hasattr(target, "message") and target.message else target
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await msg_target.reply_text(chunk, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            await msg_target.reply_text(chunk, reply_markup=markup)

async def safe_edit(status_msg, text: str):
    chunks = split_message(text)
    try:
        await status_msg.edit_text(chunks[0], parse_mode="Markdown")
    except Exception:
        try:
            await status_msg.edit_text(chunks[0])
        except Exception as e:
            logger.error(f"Failed to edit status message: {e}")
    for chunk in chunks[1:]:
        try:
            await status_msg.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            await status_msg.reply_text(chunk)

def acquire_user_request(context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """
    Acquires request concurrency lock for user before the first await.
    Returns request token if acquired, None if another request is in flight.
    """
    if context.user_data.get("is_processing"):
        return None
    token = context.user_data.get("req_token", 0) + 1
    context.user_data["req_token"] = token
    context.user_data["is_processing"] = True
    context.user_data["active_task"] = asyncio.current_task()
    return token

def is_request_current(context: ContextTypes.DEFAULT_TYPE, token: int) -> bool:
    """Checks if the request token is still active (not cancelled or superseded)."""
    return context.user_data.get("req_token") == token

def release_user_request(context: ContextTypes.DEFAULT_TYPE, token: int):
    """Safely releases processing state only if current token matches."""
    if context.user_data.get("req_token") == token:
        context.user_data["is_processing"] = False
        context.user_data["active_task"] = None

# ─────────────────────────────────────────────
# Keyboards
# ─────────────────────────────────────────────
def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main Menu showing all 6 Content Formats directly."""
    keyboard = [
        [InlineKeyboardButton(f"{ct['emoji']} {ct['name']}", callback_data=f"ctype:{cid}")]
        for cid, ct in CONTENT_TYPES.items()
    ]
    keyboard.append([
        InlineKeyboardButton("💡 គំនិត Content (Ideas)", callback_data="ideas"),
        InlineKeyboardButton("⚙️ រយៈពេលវីដេអូ", callback_data="settings"),
    ])
    keyboard.append([
        InlineKeyboardButton("🔔 Subscribe ប្រចាំថ្ងៃ", callback_data="subscribe"),
        InlineKeyboardButton("📊 ស្ថានភាពប្រព័ន្ធ", callback_data="status"),
    ])
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Settings menu for duration."""
    current = get_user_duration(chat_id)
    def mark(d):
        return f"✅ {d}" if d == current else d

    keyboard = [
        [
            InlineKeyboardButton(mark("60 វិនាទី"), callback_data="dur:60 វិនាទី"),
            InlineKeyboardButton(mark("2 នាទី"), callback_data="dur:2 នាទី"),
        ],
        [
            InlineKeyboardButton(mark("3 នាទី"), callback_data="dur:3 នាទី"),
            InlineKeyboardButton(mark("5 នាទី"), callback_data="dur:5 នាទី"),
        ],
        [
            InlineKeyboardButton("🔙 ត្រឡប់ទៅ Menu ដើម", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_done_keyboard() -> InlineKeyboardMarkup:
    """Action buttons after content is generated with Refinement tools."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎣 ប្តូរ Hook ថ្មី (៣ បែប)", callback_data="refine:hook"),
            InlineKeyboardButton("✂️ សង្ខេបឱ្យខ្លីខ្លឹម", callback_data="refine:shorten"),
        ],
        [
            InlineKeyboardButton("🔁 បង្កើតម្ដងទៀត", callback_data="refine:regen"),
            InlineKeyboardButton("🔄 ផលិត Content ថ្មី", callback_data="main_menu"),
        ],
        [
            InlineKeyboardButton("⚙️ ប្ដូររយៈពេល", callback_data="settings"),
            InlineKeyboardButton("🏠 Menu ដើម", callback_data="main_menu"),
        ],
    ])

# ─────────────────────────────────────────────
# Screen Renderers
# ─────────────────────────────────────────────
def render_welcome(chat_id: int) -> str:
    duration = get_user_duration(chat_id)
    return (
        "👋 *សួស្តី! ខ្ញុំជា 3WHs AI Content Bot* 🤖\n"
        "ជំនួយការផលិតមាតិកា Viral លើ TikTok, Reels & Shorts!\n\n"
        f"⏱️ *រយៈពេលវីដេអូបច្ចុប្បន្ន:* `{duration}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ *សូមជ្រើសរើសទម្រង់មាតិកា (Format) ដែលអ្នកចង់ផលិត៖*\n"
        "_(ចុចប៊ូតុង → Bot សួរ ១ សំណួរ → AI បង្កើតជូនភ្លាមៗ!)_"
    )

def render_settings(chat_id: int) -> str:
    duration = get_user_duration(chat_id)
    is_subbed = chat_id in subscribers
    return (
        "⚙️ *ការកំណត់រយៈពេលវីដេអូ*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"• ⏱️ រយៈពេលបច្ចុប្បន្ន៖ *{duration}*\n"
        f"• 🔔 ទទួលគំនិតប្រចាំថ្ងៃ៖ {'✅ បើក' if is_subbed else '❌ មិនទាន់'}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "_សូមជ្រើសរើសរយៈពេលវីដេអូដែលអ្នកចង់បានខាងក្រោម៖_"
    )

# ─────────────────────────────────────────────
# Command Handlers
# ─────────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Directly shows the Main Content Format Menu. Cancels pending active generation."""
    active_task = context.user_data.get("active_task")
    if active_task and not active_task.done():
        active_task.cancel()

    context.user_data["req_token"] = context.user_data.get("req_token", 0) + 1
    context.user_data["state"] = None
    context.user_data["is_processing"] = False
    context.user_data["active_task"] = None

    chat_id = update.effective_chat.id
    msg = render_welcome(chat_id)
    keyboard = get_main_menu_keyboard()
    target = update.message or (update.callback_query.message if update.callback_query else None)
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)
    except Exception:
        await target.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancels any pending action or active AI generation task.
    Preserves last successful script and metadata.
    """
    active_task = context.user_data.get("active_task")
    if active_task and not active_task.done():
        active_task.cancel()

    # Invalidate current request token so stale results will not be sent
    context.user_data["req_token"] = context.user_data.get("req_token", 0) + 1
    context.user_data["state"] = None
    context.user_data["is_processing"] = False
    context.user_data["active_task"] = None

    chat_id = update.effective_chat.id
    msg = (
        "🚫 *បានបោះបង់សំណើជោគជ័យ!* ត្រឡប់ទៅកាន់ Menu ដើមវិញ។\n"
        "_(Script ជោគជ័យចុងក្រោយរបស់អ្នកត្រូវបានរក្សាទុកដដែល)_\n\n"
        + render_welcome(chat_id)
    )
    keyboard = get_main_menu_keyboard()
    target = update.message or (update.callback_query.message if update.callback_query else None)
    await safe_reply(target, msg, reply_markup=keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *ការណែនាំប្រើប្រាស់ Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 /start — បង្ហាញ Menu ទម្រង់ Content ទាំង ៦\n"
        "🔹 /cancel — បោះបង់សំណើបច្ចុប្បន្ន និងត្រឡប់ទៅ Menu ដើម\n"
        "🔹 /ideas [វិស័យ] — គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ (ឬ /ideas ធម្មតា)\n"
        "🔹 /pace <វិនាទី> <អត្ថបទខ្មែរ> — វាស់ និងកំណត់ល្បឿននិយាយផ្ទាល់ខ្លួន\n"
        "🔹 /status — ពិនិត្យស្ថានភាពប្រព័ន្ធ, API និងល្បឿននិយាយ\n"
        "🔹 /subscribe — ទទួលគំនិតមាតិការៀងរាល់ព្រឹក\n"
        "🔹 /unsubscribe — បិទការទទួលសារប្រចាំព្រឹក\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 _គ្រាន់តែចុច /start រួចចុចលើប៊ូតុងដើម្បីជ្រើសរើស format ងាយស្រួលបំផុត!_"
    )
    target = update.message if update.message else update.callback_query.message
    await safe_reply(target, help_text)

async def ideas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message if update.message else update.callback_query.message
    token = acquire_user_request(context)
    if token is None:
        await safe_reply(target, "⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត ឬប្រើ /cancel ដើម្បីបោះបង់!")
        return

    category = " ".join(context.args).strip() if (context.args and len(context.args) > 0) else "ទូទៅ"
    status_msg = await target.reply_text("💡 *កំពុងស្វែងរកព័ត៌មានថ្មីៗ និងរៀបចំគំនិតមាតិកា...*")
    try:
        response = await ai_service.generate_daily_ideas(category)
        if not is_request_current(context, token):
            return  # Stale or cancelled request
        await safe_edit(status_msg, response)
        await target.reply_text(
            "✅ *គំនិតខាងលើ!* តើអ្នកចង់ជ្រើស Format ណាមួយដើម្បីបង្កើត Script?",
            parse_mode="Markdown",
            reply_markup=get_done_keyboard()
        )
    except asyncio.CancelledError:
        logger.info("ideas_command was cancelled")
    finally:
        release_user_request(context, token)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    duration = get_user_duration(chat_id)
    pace = get_user_pace(chat_id)
    is_subbed = chat_id in subscribers
    api_info = ai_service.get_status_info()
    text = (
        "📊 *ស្ថានភាពប្រព័ន្ធលម្អិត (System Status)*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"• ⏱️ រយៈពេលវីដេអូ: *{duration}*\n"
        f"• 🎙️ ល្បឿននិយាយប៉ាន់ស្មាន: *{pace:.1f} តួអក្សរ/វិនាទី* (កំណត់តាម /pace)\n"
        f"• 🔔 Subscribe ប្រចាំថ្ងៃ: {'✅ បើក (ម៉ោង 08:00)' if is_subbed else '❌ មិនទាន់'}\n"
        f"• 👥 អ្នក Subscribe សរុប: *{len(subscribers)} នាក់*\n"
        f"• 🔑 Gemini API Key: {'✅ បានកំណត់រួចរាល់' if api_info['configured'] else '❌ មិនទាន់កំណត់'}\n"
        f"• ⚙️ AI Engine: *{api_info['sdk']}*\n"
        f"• 🟢 ស្ថានភាព API ចុងក្រោយ: *{api_info['last_status']}*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "ℹ️ _ការផ្សាយប្រចាំថ្ងៃដំណើរការបានលុះត្រាតែ Server ដំណើរការ (Online)_.\n"
        "💡 _ប្រើ /cancel ដើម្បីបោះបង់សំណើពេលណាក៏បាន!_"
    )
    target = update.message if update.message else update.callback_query.message
    await safe_reply(target, text)

async def pace_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Calibrates user speaking pace without calling AI.
    Usage: /pace <seconds> <Khmer sample text>
    Validates finite positive seconds and sample length. Avoids silent clamping.
    """
    chat_id = update.effective_chat.id
    target = update.message if update.message else (update.callback_query.message if update.callback_query else None)

    if not context.args or len(context.args) < 2:
        help_pace = (
            "🎙️ *ការវាស់ និងកំណត់ល្បឿននិយាយផ្ទាល់ខ្លួន (Speaking Pace Calibration)*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "សូមអានអត្ថបទគំរូជាភាសាខ្មែរខាងក្រោម ដោយកំណត់ម៉ោង (Timer) នៅលើទូរស័ព្ទរបស់អ្នក រួចផ្ញើចំនួនវិនាទីដែលអ្នកបានអានចប់មកវិញ៖\n\n"
            "📝 *អត្ថបទគំរូសាកល្បង៖*\n"
            "_«សួស្តីអ្នកទាំងអស់គ្នា! ថ្ងៃនេះខ្ញុំមានគន្លឹះពិសេសមួយចង់ចែករំលែក សម្រាប់អ្នកដែលចង់ចាប់ផ្តើមផលិតមាតិកាវីដេអូខ្លីឱ្យទាក់ទាញ និងចំណេញពេលវេលា។»_\n\n"
            "👉 *របៀបវាយបញ្ជា៖*\n"
            "`/pace <ចំនួនវិនាទី> <អត្ថបទដែលអ្នកបានអាន>`\n\n"
            "_ឧទាហរណ៍៖ (ប្រសិនបើអ្នកអានអត្ថបទខាងលើចំណាយពេល 10 វិនាទី)_\n"
            "`/pace 10 សួស្តីអ្នកទាំងអស់គ្នា ថ្ងៃនេះខ្ញុំមានគន្លឹះពិសេសមួយចង់ចែករំលែក...`\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 _Bot នឹងគណនាល្បឿននិយាយរបស់អ្នក (តួអក្សរ/វិនាទី) ដើម្បីប៉ាន់ស្មានពេលវេលា Script ឱ្យកាន់តែសមស្រប!_"
        )
        await safe_reply(target, help_pace)
        return

    sec_str = context.args[0].strip()
    try:
        seconds = float(sec_str)
        if not math.isfinite(seconds) or math.isnan(seconds):
            await safe_reply(target, "⚠️ ចំនួនវិនាទីមិនត្រឹមត្រូវឡើយ (NaN ឬ Infinity ត្រូវបានបដិសេធ)។")
            return
        if seconds < 2.0 or seconds > 300.0:
            await safe_reply(target, "⚠️ សូមបញ្ចូលចំនួនវិនាទីជាក់ស្តែងចន្លោះពី 2 ដល់ 300 វិនាទី។")
            return
    except ValueError:
        await safe_reply(target, "⚠️ ចំនួនវិនាទីមិនត្រឹមត្រូវឡើយ។ ឧទាហរណ៍៖ `/pace 12 អត្ថបទ...`")
        return

    sample_text = " ".join(context.args[1:]).strip()
    units = count_khmer_dialogue_units(sample_text)
    if units < 10:
        await safe_reply(target, "⚠️ អត្ថបទខ្លីពេកក្នុងការវាស់វែង (រាប់បានត្រឹមតិចជាង 10 តួអក្សរ)។ សូមបញ្ចូលអត្ថបទគំរូពេញលេញយ៉ាងតិចពីរបីឃ្លា។")
        return

    calculated_pace = round(units / seconds, 2)
    # Check realistic speaking bounds without silent deceptive clamping
    if calculated_pace < 3.0:
        await safe_reply(
            target,
            f"⚠️ ល្បឿនគណនាបានយឺតខ្លាំងខុសធម្មតា ({calculated_pace:.1f} តួអក្សរ/s)។ "
            "សូមសាកល្បងអានម្ដងទៀតដោយប្រើល្បឿននិយាយសន្ទនាធម្មតា (conversational pace)។"
        )
        return
    if calculated_pace > 25.0:
        await safe_reply(
            target,
            f"⚠️ ល្បឿនគណនាបានលឿនខ្លាំងខុសធម្មតា ({calculated_pace:.1f} តួអក្សរ/s)។ "
            "សូមពិនិត្យមើលចំនួនវិនាទីដែលអ្នកបានកំណត់ ឬសាកល្បងអានអត្ថបទវែងជាងនេះបន្តិច។"
        )
        return

    set_user_pace(chat_id, calculated_pace)
    success_msg = (
        "✅ *បានកំណត់ល្បឿននិយាយផ្ទាល់ខ្លួនជោគជ័យ!* 🎉\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"• ⏱️ រយៈពេលអាន៖ *{seconds:.1f} វិនាទី*\n"
        f"• 📏 ចំនួនតួអក្សររាប់បាន៖ *{units} តួអក្សរ*\n"
        f"• 🎙️ ល្បឿនគណនាជាក់ស្តែង៖ *{calculated_pace:.1f} តួអក្សរ/វិនាទី*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 _ចំណាំ៖ រយៈពេលនិយាយក្នុង Script គឺសម្រាប់តែការប៉ាន់ស្មានប្រហាក់ប្រហែលប៉ុណ្ណោះ។ "
        "ល្បឿននិយាយជាក់ស្តែងនៅពេលថតអាចប្រែប្រួលតាមអារម្មណ៍ ការសង្កត់សំឡេង និងការផ្អាក (pauses)។_"
    )
    await safe_reply(target, success_msg)

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    save_subscribers(subscribers)
    msg = (
        "✅ *Subscribe ជោគជ័យ!* 🎉\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Bot នឹងផ្ញើគំនិត Content & Script 3WHs ថ្មីៗ\n"
        "ជារៀងរាល់ព្រឹក ម៉ោង *08:00* ដោយស្វ័យប្រវត្តិ 🚀"
    )
    if update.callback_query:
        await update.callback_query.answer("Subscribe ជោគជ័យ! ✅")
    target = update.message if update.message else update.callback_query.message
    await safe_reply(target, msg)

async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers(subscribers)
        msg = "🔕 *បានបិទ Subscribe រួចរាល់!*"
    else:
        msg = "ℹ️ អ្នកមិនទាន់បាន Subscribe នៅឡើយទេ។"
    target = update.message if update.message else update.callback_query.message
    await safe_reply(target, msg)

# ─────────────────────────────────────────────
# Callback Query Handler
# ─────────────────────────────────────────────
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = update.effective_chat.id

    # ── Return to Main Menu ────────────────────
    if data == "main_menu":
        context.user_data["state"] = None
        context.user_data["is_processing"] = False
        await query.answer()
        msg = render_welcome(chat_id)
        keyboard = get_main_menu_keyboard()
        try:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── Select Content Type ───────────────────
    elif data.startswith("ctype:"):
        cid = data.split(":", 1)[1]
        if cid not in CONTENT_TYPES:
            await query.answer("Content Type មិនត្រឹមត្រូវ!")
            return
        ct = CONTENT_TYPES[cid]

        # Set state: awaiting user's topic
        context.user_data["state"] = "awaiting_topic"
        context.user_data["content_type"] = cid

        await query.answer(f"{ct['emoji']} {ct['name']}")
        question_text = ct["question"]
        cancel_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 ត្រឡប់ទៅ Menu ដើម", callback_data="main_menu")
        ]])
        try:
            await query.edit_message_text(
                question_text,
                parse_mode="Markdown",
                reply_markup=cancel_keyboard
            )
        except Exception:
            await query.message.reply_text(
                question_text,
                parse_mode="Markdown",
                reply_markup=cancel_keyboard
            )

    # ── Ideas Button ──────────────────────────
    elif data == "ideas":
        token = acquire_user_request(context)
        if token is None:
            await query.answer("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!", show_alert=True)
            return
        await query.answer("💡 កំពុងរៀបចំគំនិត...")
        status_msg = await query.message.reply_text("💡 *កំពុងស្វែងរកព័ត៌មានថ្មីៗ និងរៀបចំគំនិតមាតិកា...*")
        try:
            response = await ai_service.generate_daily_ideas("ទូទៅ")
            if not is_request_current(context, token):
                return
            await safe_edit(status_msg, response)
            await query.message.reply_text(
                "✅ *គំនិតខាងលើ!* ចង់ជ្រើស Format ណាមួយដើម្បីផលិត Script?",
                parse_mode="Markdown",
                reply_markup=get_done_keyboard()
            )
        except asyncio.CancelledError:
            logger.info("ideas callback cancelled")
        finally:
            release_user_request(context, token)

    # ── Settings Button ───────────────────────
    elif data == "settings":
        await query.answer()
        msg = render_settings(chat_id)
        keyboard = get_settings_keyboard(chat_id)
        try:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── Set Duration ──────────────────────────
    elif data.startswith("dur:"):
        dur = data.split(":", 1)[1]
        set_user_duration(chat_id, dur)
        await query.answer(f"✅ បានកំណត់រយៈពេល {dur}")
        msg = render_welcome(chat_id)
        keyboard = get_main_menu_keyboard()
        try:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── Subscribe Button ──────────────────────
    elif data == "subscribe":
        await subscribe_command(update, context)

    # ── Status Button ─────────────────────────
    elif data == "status":
        await query.answer()
        await status_command(update, context)

    # ── Refine: Change Hook ───────────────────
    elif data == "refine:hook":
        last_script = context.user_data.get("last_script")
        if not last_script:
            await query.answer("មិនមាន Script មុនដើម្បីកែប្រែទេ!")
            return
        token = acquire_user_request(context)
        if token is None:
            await query.answer("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!", show_alert=True)
            return
        await query.answer("🎣 កំពុងបង្កើត Hook ថ្មី...")
        status_msg = await query.message.reply_text("🎣 *កំពុងបង្កើតជម្រើស Hook ថ្មីទាំង ៣ បែប...*")
        try:
            hook_response = await ai_service.refine_hook(last_script)
            if not is_request_current(context, token):
                return
            await safe_edit(status_msg, hook_response)
            await query.message.reply_text(
                "💡 *អ្នកអាចជ្រើស Hook ខាងលើទៅជំនួសបាន!* Script ដើមរបស់អ្នកនៅតែត្រូវបានរក្សាទុកដដែល។ តើចង់កែអ្វីបន្តទៀត?",
                parse_mode="Markdown",
                reply_markup=get_done_keyboard()
            )
        except asyncio.CancelledError:
            logger.info("refine:hook cancelled")
        finally:
            release_user_request(context, token)

    # ── Refine: Shorten ───────────────────────
    elif data == "refine:shorten":
        last_script = context.user_data.get("last_script")
        if not last_script:
            await query.answer("មិនមាន Script មុនដើម្បីកែប្រែទេ!")
            return
        token = acquire_user_request(context)
        if token is None:
            await query.answer("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!", show_alert=True)
            return
        await query.answer("✂️ កំពុងសង្ខេបឱ្យខ្លី...")
        status_msg = await query.message.reply_text("✂️ *កំពុងកែសម្រួលឱ្យខ្លី ខ្លឹម និង Fast-paced ជាងមុន...*")
        try:
            dur = context.user_data.get("last_duration", get_user_duration(chat_id))
            pace = get_user_pace(chat_id)
            plan_result: PlanResult = await ai_service.refine_shorten(last_script, dur, pace)
            if not is_request_current(context, token):
                return
            await safe_edit(status_msg, plan_result.formatted_text)
            if plan_result.success and plan_result.plan is not None:
                context.user_data["last_script"] = plan_result.formatted_text
                context.user_data["last_script_plan"] = plan_result.plan
                notice = "✅ *Script កែសម្រួលរួចរាល់!* តើចង់ធ្វើអ្វីបន្តទៀត?"
            else:
                notice = "⚠️ *ការកែសម្រួលមិនទាន់ជោគជ័យ!* Script ដើមរបស់អ្នកត្រូវបានរក្សាទុកដដែល។ អ្នកអាចសាកល្បងម្ដងទៀត:"
            await query.message.reply_text(
                notice,
                parse_mode="Markdown",
                reply_markup=get_done_keyboard()
            )
        except asyncio.CancelledError:
            logger.info("refine:shorten cancelled")
        finally:
            release_user_request(context, token)

    # ── Refine: Regenerate ────────────────────
    elif data == "refine:regen":
        last_topic = context.user_data.get("last_topic")
        last_ct = context.user_data.get("last_content_type", "3whs")
        duration = get_user_duration(chat_id)
        pace = get_user_pace(chat_id)
        if not last_topic:
            await query.answer("សូមជ្រើសរើស Content Type ជាថ្មី!")
            return
        token = acquire_user_request(context)
        if token is None:
            await query.answer("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!", show_alert=True)
            return
        ct = CONTENT_TYPES.get(last_ct, CONTENT_TYPES["3whs"])
        await query.answer("🔁 កំពុងបង្កើតម្ដងទៀត...")
        status_msg = await query.message.reply_text(
            f"🔁 *កំពុងបង្កើត {ct['emoji']} {ct['name']} ម្តងទៀត (មុំថ្មី)...*\n"
            f"_ប្រធានបទ: {last_topic}_\n"
            f"_រយៈពេល: {duration}_\n"
            f"_ល្បឿននិយាយ: {pace:.1f} chars/s_"
        )
        try:
            plan_result: PlanResult = await ai_service.generate_content_by_type(
                content_type=last_ct,
                topic=last_topic,
                niche=last_topic,
                duration=duration,
                user_pace=pace,
            )
            if not is_request_current(context, token):
                return
            await safe_edit(status_msg, plan_result.formatted_text)
            if plan_result.success and plan_result.plan is not None:
                context.user_data["last_script"] = plan_result.formatted_text
                context.user_data["last_script_plan"] = plan_result.plan
                context.user_data["last_duration"] = duration
                notice = f"✅ *{ct['emoji']} {ct['name']} (កំណែថ្មី) រួចរាល់!*"
            else:
                notice = "⚠️ *ការបង្កើតឡើងវិញមិនទាន់ជោគជ័យ!* Script ដើមត្រូវបានរក្សាទុកដដែល។ អ្នកអាចសាកល្បងម្ដងទៀត:"
            await query.message.reply_text(
                notice,
                parse_mode="Markdown",
                reply_markup=get_done_keyboard()
            )
        except asyncio.CancelledError:
            logger.info("refine:regen cancelled")
        finally:
            release_user_request(context, token)

# ─────────────────────────────────────────────
# Message Handler (State Machine)
# ─────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return

    state = context.user_data.get("state")

    # ── STATE: Awaiting user's topic for chosen format ──
    if state == "awaiting_topic":
        token = acquire_user_request(context)
        if token is None:
            await update.message.reply_text("⏳ Bot កំពុងគិត និងសរសេរ Script... សូមរង់ចាំមួយភ្លែត ឬប្រើ /cancel ដើម្បីបោះបង់!")
            return

        content_type = context.user_data.get("content_type", "3whs")
        duration = get_user_duration(update.effective_chat.id)
        ct = CONTENT_TYPES.get(content_type, CONTENT_TYPES["3whs"])

        # Clear awaiting state
        context.user_data["state"] = None

        status_msg = await update.message.reply_text(
            f"⏳ *កំពុងបង្កើត {ct['emoji']} {ct['name']}...*\n"
            f"_ប្រធានបទ/វិស័យ: {user_text}_\n"
            f"_រយៈពេល: {duration}_\n\n"
            "សូមរង់ចាំមួយភ្លែត..."
        )

        try:
            pace = get_user_pace(update.effective_chat.id)
            plan_result: PlanResult = await ai_service.generate_content_by_type(
                content_type=content_type,
                topic=user_text,
                niche=user_text,
                duration=duration,
                user_pace=pace,
            )
            if not is_request_current(context, token):
                return
            await safe_edit(status_msg, plan_result.formatted_text)

            # Store for refinement buttons ONLY if entire plan passed strict validation
            if plan_result.success and plan_result.plan is not None:
                context.user_data["last_script"] = plan_result.formatted_text
                context.user_data["last_script_plan"] = plan_result.plan
                context.user_data["last_topic"] = user_text
                context.user_data["last_content_type"] = content_type
                context.user_data["last_duration"] = duration
                notice = f"✅ *{ct['emoji']} {ct['name']} រួចរាល់!*\nតើអ្នកចង់កែសម្រួល ឬផលិត Content អ្វីបន្តទៀត?"
            else:
                notice = (
                    "⚠️ *ការបង្កើតមិនទាន់ជោគជ័យពេញលេញទេ!*\n"
                    "Script មុនរបស់អ្នក (ប្រសិនបើមាន) នៅតែត្រូវបានរក្សាទុកដដែល។ "
                    "អ្នកអាចចុច [🔁 បង្កើតម្ដងទៀត] ដើម្បីសាកល្បងម្ដងទៀត។"
                )

            await update.message.reply_text(
                notice,
                parse_mode="Markdown",
                reply_markup=get_done_keyboard()
            )
        except asyncio.CancelledError:
            logger.info("Script generation was cancelled")
        finally:
            release_user_request(context, token)

    # ── Default: Free-text AI chat ────────────
    else:
        token = acquire_user_request(context)
        if token is None:
            await update.message.reply_text("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!")
            return
        try:
            await update.message.chat.send_action("typing")
            response = await ai_service.chat(user_text)
            if not is_request_current(context, token):
                return
            await safe_reply(update.message, response)
        except asyncio.CancelledError:
            logger.info("Chat response was cancelled")
        finally:
            release_user_request(context, token)

# ─────────────────────────────────────────────
# Daily Scheduler Broadcast
# ─────────────────────────────────────────────
async def send_daily_content(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Daily broadcast starting...")
    if not subscribers:
        return
    try:
        # Generate ideas ONCE for all subscribers to save quota
        content = await ai_service.generate_daily_ideas("ទូទៅ")
        if not content or content.startswith("⚠️") or content.startswith("❌"):
            logger.warning("Daily broadcast generated an error response, aborting broadcast.")
            return

        msg = (
            "☀️ *អរុណសួស្តី! គំនិតមាតិកាប្រចាំថ្ងៃ* 💡\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{content}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 _ចុច /start ដើម្បីជ្រើសរើស Content Type រួចបង្កើត Script ភ្លាមៗ!_"
        )
        chunks = split_message(msg)
        for chat_id in list(subscribers):
            for chunk in chunks:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id, text=chunk, parse_mode="Markdown"
                    )
                except Exception:
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=chunk)
                    except Exception as e:
                        logger.error(f"Daily broadcast failed for {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Daily broadcast error: {e}")

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("\nERROR: TELEGRAM_BOT_TOKEN not set in .env\n")
        return

    start_health_check_server()
    # concurrent_updates(True) allows /cancel and other updates while I/O is pending
    application = ApplicationBuilder().token(token).concurrent_updates(True).build()

    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ideas", ideas_command))
    application.add_handler(CommandHandler("pace", pace_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CommandHandler("status", status_command))

    # Buttons & Messages
    application.add_handler(CallbackQueryHandler(button_callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Daily scheduler with JobQueue verification
    daily_time_str = os.getenv("DAILY_TIME", "08:00")
    timezone_str = os.getenv("TIMEZONE", "Asia/Phnom_Penh")
    try:
        hour, minute = map(int, daily_time_str.split(":"))
        tz = pytz.timezone(timezone_str)
        scheduled_time = time(hour=hour, minute=minute, tzinfo=tz)
        if application.job_queue:
            application.job_queue.run_daily(send_daily_content, time=scheduled_time)
            logger.info(f"Daily job scheduled at {daily_time_str} ({timezone_str})")
        else:
            logger.error(
                "CRITICAL: JobQueue is NOT available on this Telegram Application. "
                "Daily scheduled broadcasts will NOT run! "
                "Ensure python-telegram-bot is installed with job-queue extra: "
                "pip install \"python-telegram-bot[job-queue]\""
            )
    except Exception as e:
        logger.error(f"Scheduler error: {e}")

    print("\n" + "=" * 50)
    print("3WHs Telegram Bot Agent - Running (Direct Format Menu)...")
    print("Go to Telegram and press /start !")
    print("=" * 50 + "\n")

    application.run_polling()

if __name__ == "__main__":
    main()
