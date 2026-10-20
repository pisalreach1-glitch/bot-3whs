import os
import sys
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import time
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
        logger.info(f"Health check server on port {port}")
    except Exception as e:
        logger.error(f"Health check server error: {e}")

# ─────────────────────────────────────────────
# Projects Config
# ─────────────────────────────────────────────
PROJECTS = {
    "3whs": {
        "id": "3whs",
        "emoji": "🎬",
        "name": "3WHs Content",
        "niche": "3WHs Video Content",
        "description": "Script / Content ទូទៅ TikTok & Reels",
        "default_duration": "60 វិនាទី",
    },
    "haknheng": {
        "id": "haknheng",
        "emoji": "🍳",
        "name": "សាលាហ្វឹកហ្វែន ហាក់ហេង",
        "niche": "សាលាបង្រៀនធ្វើម្ហូបហាក់ហេង",
        "description": "Content ម្ហូបខ្មែរ + ការបង្រៀន",
        "default_duration": "60 វិនាទី",
    },
}

# ─────────────────────────────────────────────
# Content Types Config
# ─────────────────────────────────────────────
CONTENT_TYPES = {
    "3whs": {
        "emoji": "🎬",
        "name": "3WHs Hook Script",
        "description": "Script Video ពេញលេញ (Hook→What→Why→How→CTA)",
        "question": (
            "🎬 *3WHs Hook Script*\n\n"
            "📝 *សូមប្រាប់ប្រធានបទ ឬទិដ្ឋភាព* ដែលអ្នកចង់ធ្វើ Script:\n\n"
            "_ឧទាហរណ៍:_\n"
            "• «វិធីធ្វើបាយឆា ១០ នាទី»\n"
            "• «៣ ជំហានជ្រើសម្ហូបស្រស់»\n"
            "• «ហេតុអ្វីហ្វឹកហ្វែនម្ហូបសំខាន់»"
        ),
    },
    "pov": {
        "emoji": "🎭",
        "name": "POV / Storytelling",
        "description": "Story ពិត ទាក់ Emotion + Watch Time ខ្ពស់",
        "question": (
            "🎭 *POV / Storytelling*\n\n"
            "📝 *POV ស្ថានភាព ឬ Story* ដែលអ្នកចង់ Play:\n\n"
            "_ឧទាហរណ៍:_\n"
            "• «POV: ថ្ងៃដំបូងខ្ញុំចូលរៀនធ្វើម្ហូប»\n"
            "• «ពេលដែរ Customer ដំបូងចូលហាង»\n"
            "• «POV: ខ្ញុំធ្វើបដិបត្តិការ ១ ម្ហូប ១ ថ្ងៃ»"
        ),
    },
    "myth": {
        "emoji": "⚡",
        "name": "Myth vs Reality",
        "description": "បំបែក Misconception → Comment ច្រើន + Viral",
        "question": (
            "⚡ *Myth vs Reality*\n\n"
            "📝 *ការយល់ច្រឡំ ឬ Myth* ដែលអ្នកចង់បំបែក:\n\n"
            "_ឧទាហរណ៍:_\n"
            "• «ម្ហូបខ្មែរ ធ្វើពិបាក ចំណាយពេល»\n"
            "• «ហ្វឹកហ្វែនម្ហូបត្រូវចំណាយថ្លៃ»\n"
            "• «Chef ល្អ ត្រូវចេះ Recipe ច្រើន»"
        ),
    },
    "transform": {
        "emoji": "🔄",
        "name": "Before & After",
        "description": "Transformation Visual → Save + Share ច្រើន",
        "question": (
            "🔄 *Before & After*\n\n"
            "📝 *ការផ្លាស់ប្ដូរ ឬ Transformation* ដែលអ្នកចង់បង្ហាញ:\n\n"
            "_ឧទាហរណ៍:_\n"
            "• «មុន-ក្រោយ រៀនម្ហូប ៣០ ថ្ងៃ»\n"
            "• «គ្រឿងផ្សំ Raw → មុខម្ហូបស្រស់ស្អាត»\n"
            "• «Student ដំបូង → Chef ក្នុង ១ ខែ»"
        ),
    },
    "hottake": {
        "emoji": "🌶️",
        "name": "Hot Take / Opinion",
        "description": "Controversial Opinion → Debate → Algorithm Boost",
        "question": (
            "🌶️ *Hot Take / Opinion*\n\n"
            "📝 *មតិ ឬ Opinion* ដែរអ្នកចង់ចែករំលែក:\n\n"
            "_ឧទាហរណ៍:_\n"
            "• «ហ្វឹកហ្វែនម្ហូប Online ល្អជាង Offline»\n"
            "• «ម្ហូប Fusion ចំណោះ Overrated»\n"
            "• «Creator ម្ហូបខ្មែរ ធ្វើ Content ខ្លាំងជាង»"
        ),
    },
    "toplist": {
        "emoji": "📋",
        "name": "Top List / Ranking",
        "description": "List / Ranking → Save ច្រើន + Comment",
        "question": (
            "📋 *Top List / Ranking*\n\n"
            "📝 *Top ប៉ុន្មាន? ប្រភេទ/ប្រធានបទអ្វី?*\n\n"
            "_ឧទាហរណ៍:_\n"
            "• «Top 5 ម្ហូបខ្មែរ ដែរឆ្ងាញ់គ្រប់ Season»\n"
            "• «7 Mistakes Student ថ្មីតែងធ្វើ»\n"
            "• «3 ហ្វឹកហ្វែន ដែរ ROI ខ្ពស់»"
        ),
    },
}

DEFAULT_PROJECT_ID = "3whs"
DEFAULT_DURATION = "60 វិនាទី"
DEFAULT_DAILY_TIME = "5:00 ព្រឹក"

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

def get_user_config(chat_id: int) -> dict:
    str_id = str(chat_id)
    if str_id not in user_settings:
        user_settings[str_id] = {
            "project_id": DEFAULT_PROJECT_ID,
            "duration": DEFAULT_DURATION,
            "daily_time": DEFAULT_DAILY_TIME,
            "niche": PROJECTS[DEFAULT_PROJECT_ID]["niche"],
        }
        save_user_settings_to_file(user_settings)
    return user_settings[str_id]

def update_user_config(chat_id: int, key: str, value: str):
    cfg = get_user_config(chat_id)
    cfg[key] = value
    user_settings[str(chat_id)] = cfg
    save_user_settings_to_file(user_settings)

def get_active_project(chat_id: int) -> dict:
    cfg = get_user_config(chat_id)
    pid = cfg.get("project_id", DEFAULT_PROJECT_ID)
    return PROJECTS.get(pid, PROJECTS[DEFAULT_PROJECT_ID])

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
# Helpers
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
    msg_target = (
        target.message if hasattr(target, "message") and target.message else target
    )
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
            logger.error(f"Failed to edit: {e}")
    for chunk in chunks[1:]:
        try:
            await status_msg.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            await status_msg.reply_text(chunk)

# ─────────────────────────────────────────────
# Keyboards
# ─────────────────────────────────────────────
def get_project_selector_keyboard() -> InlineKeyboardMarkup:
    """Step 1: Choose a Project."""
    keyboard = [
        [InlineKeyboardButton(
            f"{proj['emoji']} {proj['name']}",
            callback_data=f"project:{pid}"
        )]
        for pid, proj in PROJECTS.items()
    ]
    return InlineKeyboardMarkup(keyboard)

def get_content_type_keyboard(project_id: str) -> InlineKeyboardMarkup:
    """Step 2: Choose a Content Type."""
    type_buttons = [
        [
            InlineKeyboardButton(
                f"{ct['emoji']} {ct['name']}",
                callback_data=f"ctype:{project_id}:{cid}"
            )
        ]
        for cid, ct in CONTENT_TYPES.items()
    ]
    # Bottom row: utilities
    type_buttons.append([
        InlineKeyboardButton("💡 Ideas ស្វ័យប្រវត្ត", callback_data=f"ideas:{project_id}"),
        InlineKeyboardButton("⚙️ ការកំណត់", callback_data=f"settings:{project_id}"),
    ])
    type_buttons.append([
        InlineKeyboardButton("🔙 ជ្រើស Project ម្ដងទៀត", callback_data="back_projects"),
    ])
    return InlineKeyboardMarkup(type_buttons)

def get_settings_keyboard(project_id: str) -> InlineKeyboardMarkup:
    """Settings sub-menu."""
    keyboard = [
        [
            InlineKeyboardButton("⚡ 60 វិនាទី", callback_data=f"dur:{project_id}:60 វិនាទី"),
            InlineKeyboardButton("🎯 2 នាទី", callback_data=f"dur:{project_id}:2 នាទី"),
        ],
        [
            InlineKeyboardButton("🎬 3 នាទី", callback_data=f"dur:{project_id}:3 នាទី"),
            InlineKeyboardButton("🎥 5 នាទី", callback_data=f"dur:{project_id}:5 នាទី"),
        ],
        [
            InlineKeyboardButton("🔔 Subscribe ប្រចាំថ្ងៃ", callback_data=f"subscribe:{project_id}"),
            InlineKeyboardButton("📊 Status", callback_data=f"status:{project_id}"),
        ],
        [
            InlineKeyboardButton("🔙 ត្រឡប់", callback_data=f"project:{project_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_done_keyboard(project_id: str) -> InlineKeyboardMarkup:
    """After content is generated — quick next actions."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Content Type ថ្មី", callback_data=f"project:{project_id}"),
            InlineKeyboardButton("🏠 Menu ដើម", callback_data="back_projects"),
        ]
    ])

# ─────────────────────────────────────────────
# Screen Renderers
# ─────────────────────────────────────────────
def render_welcome() -> str:
    lines = [
        "👋 *សួស្តី! ខ្ញុំជា 3WHs AI Content Bot* 🤖",
        "",
        "📂 *សូមជ្រើសរើស Project:*",
        "━━━━━━━━━━━━━━━━━━",
    ]
    for proj in PROJECTS.values():
        lines.append(f"{proj['emoji']} *{proj['name']}* — {proj['description']}")
    lines += ["━━━━━━━━━━━━━━━━━━", "_👇 ចុចជ្រើស Project ខាងក្រោម_"]
    return "\n".join(lines)

def render_content_type_menu(project_id: str, chat_id: int) -> str:
    proj = PROJECTS.get(project_id, PROJECTS[DEFAULT_PROJECT_ID])
    cfg = get_user_config(chat_id)
    duration = cfg.get("duration", proj["default_duration"])
    return (
        f"{proj['emoji']} *{proj['name']}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *វិស័យ:* {proj['niche']}\n"
        f"⏱️ *រយៈពេល:* {duration}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✨ *ជ្រើស Content Format ដែលអ្នកចង់បង្កើត:*\n"
        f"_(ចុចប៊ូតុង → Bot សួរ ១ សំណួរ → Generate ភ្លាម!)_"
    )

def render_settings_menu(project_id: str, chat_id: int) -> str:
    proj = PROJECTS.get(project_id, PROJECTS[DEFAULT_PROJECT_ID])
    cfg = get_user_config(chat_id)
    duration = cfg.get("duration", proj["default_duration"])
    is_subbed = chat_id in subscribers
    return (
        f"⚙️ *ការកំណត់* — {proj['emoji']} {proj['name']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏱️ *រយៈពេលបច្ចុប្បន្ន:* {duration}\n"
        f"🔔 *Subscribe:* {'✅ បើក' if is_subbed else '❌ មិនទាន់'}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"_ចុចជ្រើសរយៈពេលខាងក្រោម:_"
    )

# ─────────────────────────────────────────────
# Command Handlers
# ─────────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the Project Selector (Step 1)."""
    # Clear any pending state
    context.user_data.clear()
    msg = render_welcome()
    keyboard = get_project_selector_keyboard()
    target = update.message or update.callback_query.message
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)
    except Exception:
        await target.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Commands*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🔹 /start — Menu ជ្រើស Project\n"
        "🔹 /ideas — គំនិតប្រធានបទថ្ងៃនេះ\n"
        "🔹 /status — ស្ថានភាពប្រព័ន្ធ\n"
        "🔹 /subscribe — Subscribe ប្រចាំថ្ងៃ\n"
        "🔹 /unsubscribe — បិទ Subscribe\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 _ប្រើ /start → ចុចប៊ូតុង ងាយជាងវាយ Command!_"
    )
    target = update.message if update.message else update.callback_query.message
    await safe_reply(target, help_text)

async def ideas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    proj = get_active_project(chat_id)
    target = update.message if update.message else update.callback_query.message
    status_msg = await target.reply_text(
        f"💡 *កំពុងបង្កើតគំនិត* {proj['emoji']} *{proj['name']}*..."
    )
    response = await ai_service.generate_daily_ideas(proj["niche"])
    await safe_edit(status_msg, response)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cfg = get_user_config(chat_id)
    proj = get_active_project(chat_id)
    is_subbed = chat_id in subscribers
    is_ai_ok = ai_service.is_configured()
    text = (
        "📊 *System Status*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"• 📂 Project: *{proj['emoji']} {proj['name']}*\n"
        f"• 🎯 វិស័យ: *{proj['niche']}*\n"
        f"• ⏱️ រយៈពេល: *{cfg.get('duration', proj['default_duration'])}*\n"
        f"• 🔔 Subscribe: {'✅ បើក' if is_subbed else '❌ មិនទាន់'}\n"
        f"• 🧠 AI: {'🟢 ដំណើរការ' if is_ai_ok else '🔴 គ្មាន Key'}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    target = update.message if update.message else update.callback_query.message
    await safe_reply(target, text)

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    save_subscribers(subscribers)
    cfg = get_user_config(chat_id)
    daily_time = cfg.get("daily_time", DEFAULT_DAILY_TIME)
    msg = (
        "✅ *Subscribe ជោគជ័យ!* 🎉\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Bot នឹងផ្ញើ Ideas & Script 3WHs ថ្មីៗ\n"
        f"ជារៀងរាល់ព្រឹក ម៉ោង *{daily_time}* ដោយស្វ័យប្រវត្ត 🚀"
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
        msg = "🔕 *បិទ Subscribe ជោគជ័យ!*"
    else:
        msg = "ℹ️ អ្នកមិនទាន់ Subscribe នៅឡើយទេ។"
    target = update.message if update.message else update.callback_query.message
    await safe_reply(target, msg)

# ─────────────────────────────────────────────
# Callback Query Handler
# ─────────────────────────────────────────────
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = update.effective_chat.id

    # ── STEP 1: Project Select ─────────────────
    if data.startswith("project:"):
        pid = data.split(":", 1)[1]
        if pid not in PROJECTS:
            await query.answer("Project មិនមាន!")
            return
        proj = PROJECTS[pid]
        # Save active project
        update_user_config(chat_id, "project_id", pid)
        update_user_config(chat_id, "niche", proj["niche"])
        # Clear any pending state
        context.user_data.clear()

        msg = render_content_type_menu(pid, chat_id)
        keyboard = get_content_type_keyboard(pid)
        await query.answer(f"{proj['emoji']} {proj['name']}")
        try:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── Back to Project List ───────────────────
    elif data == "back_projects":
        context.user_data.clear()
        await query.answer()
        msg = render_welcome()
        keyboard = get_project_selector_keyboard()
        try:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── STEP 2: Content Type Select ───────────
    elif data.startswith("ctype:"):
        _, pid, cid = data.split(":", 2)
        if cid not in CONTENT_TYPES:
            await query.answer("Content Type មិនមាន!")
            return
        ct = CONTENT_TYPES[cid]

        # Set state: waiting for user's topic answer
        context.user_data["state"] = "awaiting_topic"
        context.user_data["content_type"] = cid
        context.user_data["project_id"] = pid

        await query.answer(f"{ct['emoji']} {ct['name']}")
        # Ask the 1 targeted question
        question_text = ct["question"]
        cancel_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 ត្រឡប់", callback_data=f"project:{pid}")
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

    # ── Ideas (Auto, no question) ──────────────
    elif data.startswith("ideas:"):
        pid = data.split(":", 1)[1]
        proj = PROJECTS.get(pid, PROJECTS[DEFAULT_PROJECT_ID])
        await query.answer("💡 កំពុងបង្កើតគំនិត...")
        status_msg = await query.message.reply_text(
            f"💡 *កំពុងបង្កើត Ideas* {proj['emoji']} *{proj['name']}*..."
        )
        response = await ai_service.generate_daily_ideas(proj["niche"])
        await safe_edit(status_msg, response)
        # Show done keyboard
        await query.message.reply_text(
            "✅ *Ideas ខាងលើ!* ចង់ធ្វើ Content ផ្សេងទៀត?",
            parse_mode="Markdown",
            reply_markup=get_done_keyboard(pid)
        )

    # ── Settings ──────────────────────────────
    elif data.startswith("settings:"):
        pid = data.split(":", 1)[1]
        await query.answer()
        msg = render_settings_menu(pid, chat_id)
        keyboard = get_settings_keyboard(pid)
        try:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── Duration Quick Pick ────────────────────
    elif data.startswith("dur:"):
        parts = data.split(":", 2)
        pid, dur = parts[1], parts[2]
        update_user_config(chat_id, "duration", dur)
        await query.answer(f"✅ ប្ដូរទៅ {dur}")
        # Go back to content type menu
        msg = render_content_type_menu(pid, chat_id)
        keyboard = get_content_type_keyboard(pid)
        try:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── Subscribe ─────────────────────────────
    elif data.startswith("subscribe:"):
        await subscribe_command(update, context)

    # ── Status ────────────────────────────────
    elif data.startswith("status:"):
        await query.answer()
        await status_command(update, context)

# ─────────────────────────────────────────────
# Message Handler (State Machine)
# ─────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return

    state = context.user_data.get("state")

    # ── STATE: Awaiting topic for content generation ──
    if state == "awaiting_topic":
        content_type = context.user_data.get("content_type", "3whs")
        project_id = context.user_data.get("project_id", DEFAULT_PROJECT_ID)
        proj = PROJECTS.get(project_id, PROJECTS[DEFAULT_PROJECT_ID])
        cfg = get_user_config(update.effective_chat.id)
        duration = cfg.get("duration", proj["default_duration"])
        ct = CONTENT_TYPES.get(content_type, CONTENT_TYPES["3whs"])

        # Clear state immediately
        context.user_data.clear()

        # Show generating status
        status_msg = await update.message.reply_text(
            f"⏳ *កំពុងបង្កើត {ct['emoji']} {ct['name']}...*\n"
            f"_វិស័យ: {proj['niche']}_\n"
            f"_ប្រវែង: {duration}_"
        )

        # Generate content
        response = await ai_service.generate_content_by_type(
            content_type=content_type,
            topic=user_text,
            niche=proj["niche"],
            duration=duration,
        )
        await safe_edit(status_msg, response)

        # Show quick action buttons after done
        await update.message.reply_text(
            f"✅ *{ct['emoji']} {ct['name']} ខាងលើ!*\n"
            "ចង់ធ្វើ Content ផ្សេងទៀតទេ?",
            parse_mode="Markdown",
            reply_markup=get_done_keyboard(project_id)
        )

    # ── Default: Free-text AI chat ───────────
    else:
        await update.message.chat.send_action("typing")
        response = await ai_service.chat(user_text)
        await safe_reply(update.message, response)

# ─────────────────────────────────────────────
# Daily Scheduler Broadcast
# ─────────────────────────────────────────────
async def send_daily_content(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Daily broadcast starting...")
    if not subscribers:
        return
    for chat_id in list(subscribers):
        try:
            proj = get_active_project(chat_id)
            content = await ai_service.generate_daily_ideas(proj["niche"])
            msg = (
                f"☀️ *អរុណសួស្តី!* {proj['emoji']}\n"
                f"*{proj['name']}* — Ideas ថ្ងៃនេះ:\n\n"
                f"{content}\n\n"
                f"💡 _ចុច /start → ជ្រើស Content Type → Generate Script ភ្លាម!_"
            )
            await context.bot.send_message(
                chat_id=chat_id, text=msg, parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Daily broadcast failed for {chat_id}: {e}")

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("\nERROR: TELEGRAM_BOT_TOKEN not set in .env\n")
        return

    start_health_check_server()
    application = ApplicationBuilder().token(token).build()

    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ideas", ideas_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CommandHandler("status", status_command))

    # Buttons & Messages
    application.add_handler(CallbackQueryHandler(button_callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Daily scheduler
    daily_time_str = os.getenv("DAILY_TIME", "05:00")
    timezone_str = os.getenv("TIMEZONE", "Asia/Phnom_Penh")
    try:
        hour, minute = map(int, daily_time_str.split(":"))
        tz = pytz.timezone(timezone_str)
        scheduled_time = time(hour=hour, minute=minute, tzinfo=tz)
        if application.job_queue:
            application.job_queue.run_daily(send_daily_content, time=scheduled_time)
            logger.info(f"Daily job at {daily_time_str} ({timezone_str})")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")

    print("\n" + "=" * 50)
    print("3WHs Telegram Bot Agent - Running...")
    print("Go to Telegram and press /start !")
    print("=" * 50 + "\n")

    application.run_polling()

if __name__ == "__main__":
    main()
