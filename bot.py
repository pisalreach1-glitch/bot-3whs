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

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize AI Service
ai_service = AIService()

# Health Check Server for Render.com Free Web Service
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("🎬 3WHs Telegram Bot is Running 24/7 on Render!".encode("utf-8"))

    def log_message(self, format, *args):
        # Silence access logs to keep terminal clean
        return

def start_health_check_server():
    port_str = os.getenv("PORT")
    if not port_str:
        return
    try:
        port = int(port_str)
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Health check HTTP server running on port {port}")
    except Exception as e:
        logger.error(f"Failed to start health check server on port {port_str}: {e}")

# Database for subscribed users and user settings (JSON files)
SUBSCRIBERS_FILE = "subscribers.json"
USER_SETTINGS_FILE = "user_settings.json"

DEFAULT_NICHE = "សាលាបង្រៀនធ្វើម្ហូបហាក់ហេង"
DEFAULT_DURATION = "60 វិនាទី"
DEFAULT_DAILY_TIME = "5:00 ព្រឹក"

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
            "niche": DEFAULT_NICHE,
            "duration": DEFAULT_DURATION,
            "daily_time": DEFAULT_DAILY_TIME
        }
        save_user_settings_to_file(user_settings)
    return user_settings[str_id]

def update_user_config(chat_id: int, key: str, value: str):
    cfg = get_user_config(chat_id)
    cfg[key] = value
    user_settings[str(chat_id)] = cfg
    save_user_settings_to_file(user_settings)

def load_subscribers() -> set:
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("subscribers", []))
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

def split_message(text: str, max_length: int = 4000) -> list[str]:
    """Splits message text into chunks of at most max_length characters."""
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

async def safe_reply(message_or_update, text: str, reply_markup=None):
    """Safely replies with fallback to plain text if Markdown parsing fails."""
    chunks = split_message(text)
    msg_target = message_or_update.message if hasattr(message_or_update, "message") and message_or_update.message else message_or_update
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await msg_target.reply_text(chunk, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            await msg_target.reply_text(chunk, reply_markup=markup)

async def safe_edit(status_msg, text: str):
    """Safely edits message with fallback for long messages or markdown errors."""
    chunks = split_message(text)
    try:
        await status_msg.edit_text(chunks[0], parse_mode="Markdown")
    except Exception:
        try:
            await status_msg.edit_text(chunks[0])
        except Exception as e:
            logger.error(f"Failed to edit status message: {e}")
    for extra_chunk in chunks[1:]:
        try:
            await status_msg.reply_text(extra_chunk, parse_mode="Markdown")
        except Exception:
            await status_msg.reply_text(extra_chunk)

def get_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("⚡ បង្កើត Script ឥឡូវនេះ (/now)", callback_data="btn_now"),
            InlineKeyboardButton("💡 គំនិតប្រធានបទ (/ideas)", callback_data="btn_ideas")
        ],
        [
            InlineKeyboardButton("🎯 ប្តូរវិស័យ (/setniche)", callback_data="btn_guide_niche"),
            InlineKeyboardButton("⏱️ ប្តូររយៈពេល (/setduration)", callback_data="btn_guide_duration")
        ],
        [
            InlineKeyboardButton("🔔 ទទួលសាររាល់ព្រឹក", callback_data="btn_subscribe"),
            InlineKeyboardButton("📖 ការណែនាំ (Help)", callback_data="btn_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def render_start_message(chat_id: int) -> str:
    cfg = get_user_config(chat_id)
    niche = cfg.get("niche", DEFAULT_NICHE)
    duration = cfg.get("duration", DEFAULT_DURATION)
    daily_time = cfg.get("daily_time", DEFAULT_DAILY_TIME)

    return (
        "👋 **សួស្តី! ខ្ញុំជាជំនួយការតែង Script វីដេអូ 3WHs** 🎬\n\n"
        "⚙️ **ការកំណត់បច្ចុប្បន្នរបស់អ្នក៖**\n"
        f"• 🎯 **វិស័យ៖** {niche}\n"
        f"• ⏱️ **រយៈពេលវីដេអូ៖** {duration}\n"
        f"• ⏰ **ម៉ោងផ្ញើស្វ័យប្រវត្ត៖** ម៉ោង {daily_time} រាល់ថ្ងៃ\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "💡 **តើអ្នកចង់ធ្វើអ្វីឥឡូវនេះ?**\n\n"
        "1️⃣ **បង្កើត Script តាមប្រធានបទដែលអ្នកចង់បាន៖**\n"
        "   👉 វាយពាក្យ៖ `/gen [ប្រធានបទ]`\n"
        "   *ឧទាហរណ៍៖* `/gen សាលាបង្រៀនធ្វើម្ហូប`\n\n"
        "2️⃣ **ប្តូរវិស័យផ្តោតចម្បង៖**\n"
        "   👉 វាយពាក្យ៖ `/setniche [ឈ្មោះវិស័យ]`\n"
        "   *ឧទាហរណ៍៖* `/setniche អាហារ & ភេសជ្ជៈ`\n\n"
        "3️⃣ **ប្តូររយៈពេលវីដេអូ (60s, 2m, 3m):**\n"
        "   👉 វាយពាក្យ៖ `/setduration [រយៈពេល]`\n"
        "   *ឧទាហរណ៍៖* `/setduration 2 នាទី`\n\n"
        "4️⃣ **បង្កើត Script ថ្ងៃនេះភ្លាមៗ៖**\n"
        "   👉 វាយពាក្យ៖ `/now`"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = render_start_message(chat_id)
    if update.message:
        await update.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            msg,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cfg = get_user_config(chat_id)
    default_dur = cfg.get("duration", DEFAULT_DURATION)

    if not context.args:
        guide = (
            "⚠️ **សូមបញ្ជាក់ប្រធានបទដែលអ្នកចង់បង្កើត Script!**\n\n"
            "👉 **របៀបវាយ៖** `/gen [ប្រធានបទ]`\n"
            "   *ឧទាហរណ៍៖* `/gen វិធីធ្វើស៊ុបមាន់ពិសេសសម្រាប់ហាង` ឬ `/gen គន្លឹះជ្រើសរើសសាច់ស្រស់`"
        )
        await safe_reply(update.message, guide)
        return

    full_text = " ".join(context.args)
    status_msg = await update.message.reply_text(f"⏳ កំពុងតែង Script 3WHs ប្រវែង [{default_dur}] ជូនអ្នក...")

    response = await ai_service.generate_script(full_text, default_dur)
    await safe_edit(status_msg, response)

async def now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cfg = get_user_config(chat_id)
    niche = cfg.get("niche", DEFAULT_NICHE)
    duration = cfg.get("duration", DEFAULT_DURATION)

    if update.message:
        status_msg = await update.message.reply_text(f"🚀 កំពុងបង្កើត Script 3WHs ថ្ងៃនេះសម្រាប់ [{niche}] ប្រវែង [{duration}]...")
    else:
        status_msg = await update.callback_query.message.reply_text(f"🚀 កំពុងបង្កើត Script 3WHs ថ្ងៃនេះសម្រាប់ [{niche}] ប្រវែង [{duration}]...")

    prompt_topic = f"ប្រធានបទវីដេអូទាក់ទាញ និងពេញនិយមសម្រាប់វិស័យ៖ {niche}"
    response = await ai_service.generate_script(prompt_topic, duration)
    await safe_edit(status_msg, response)

async def setniche_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        guide = (
            "🎯 **របៀបប្តូរវិស័យផ្តោតចម្បង (Niche)**\n\n"
            "👉 វាយពាក្យ៖ `/setniche [ឈ្មោះវិស័យរបស់អ្នក]`\n"
            "   *ឧទាហរណ៍៖* `/setniche សាលាបង្រៀនធ្វើម្ហូបហាក់ហេង`\n"
            "   *ឧទាហរណ៍៖* `/setniche អចលនទ្រព្យ និងសំណង់`\n"
            "   *ឧទាហរណ៍៖* `/setniche ស្ថាបត្យកម្ម SketchUp`"
        )
        await safe_reply(update.message, guide)
        return

    new_niche = " ".join(context.args)
    update_user_config(chat_id, "niche", new_niche)
    msg = (
        f"✅ **បានផ្លាស់ប្តូរវិស័យជោគជ័យ!**\n\n"
        f"• 🎯 វិស័យថ្មីរបស់អ្នក៖ **{new_niche}**\n\n"
        f"👉 វាយ `/now` ដើម្បីបង្កើត Script សម្រាប់វិស័យនេះភ្លាមៗ!"
    )
    await safe_reply(update.message, msg)

async def setduration_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        guide = (
            "⏱️ **របៀបប្តូររយៈពេលវីដេអូ (Video Duration)**\n\n"
            "👉 វាយពាក្យ៖ `/setduration [រយៈពេល]`\n"
            "   *ឧទាហរណ៍៖* `/setduration 60 វិនាទី`\n"
            "   *ឧទាហរណ៍៖* `/setduration 2 នាទី`\n"
            "   *ឧទាហរណ៍៖* `/setduration 3 នាទី`\n"
            "   *ឧទាហរណ៍៖* `/setduration 5 នាទី`"
        )
        await safe_reply(update.message, guide)
        return

    new_duration = " ".join(context.args)
    update_user_config(chat_id, "duration", new_duration)
    msg = (
        f"✅ **បានផ្លាស់ប្តូររយៈពេលវីដេអូជោគជ័យ!**\n\n"
        f"• ⏱️ រយៈពេលវីដេអូថ្មី៖ **{new_duration}**\n\n"
        f"👉 វាយ `/now` ឬ `/gen [ប្រធានបទ]` ដើម្បីចាប់ផ្តើម!"
    )
    await safe_reply(update.message, msg)

async def ideas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cfg = get_user_config(chat_id)
    niche = " ".join(context.args) if context.args else cfg.get("niche", DEFAULT_NICHE)
    
    if update.message:
        status_msg = await update.message.reply_text(f"💡 កំពុងស្វែងរកគំនិត 3WHs សម្រាប់វិស័យ [{niche}]...")
    else:
        status_msg = await update.callback_query.message.reply_text(f"💡 កំពុងស្វែងរកគំនិត 3WHs សម្រាប់វិស័យ [{niche}]...")

    response = await ai_service.generate_daily_ideas(niche)
    await safe_edit(status_msg, response)

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    save_subscribers(subscribers)
    cfg = get_user_config(chat_id)
    daily_time = cfg.get("daily_time", DEFAULT_DAILY_TIME)
    msg = (
        "✅ **បានចុះឈ្មោះជោគជ័យ!** 🎉\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"ខ្ញុំនឹងផ្ញើគំនិតមាតិកា និង Script 3WHs ថ្មីៗមកកាន់អ្នកជារៀងរាល់ព្រឹកនៅម៉ោង **{daily_time}**។ 🚀"
    )
    if update.message:
        await safe_reply(update.message, msg)
    elif update.callback_query:
        await update.callback_query.answer("ចុះឈ្មោះជោគជ័យ!")
        await safe_reply(update.callback_query.message, msg)

async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers(subscribers)
        msg = "🔕 **អ្នកបានផ្អាកការទទួលមាតិកាប្រចាំថ្ងៃដោយជោគជ័យ។**"
    else:
        msg = "ℹ️ អ្នកមិនទាន់បាន Subscribe នៅឡើយទេ។"

    if update.message:
        await safe_reply(update.message, msg)
    elif update.callback_query:
        await update.callback_query.answer()
        await safe_reply(update.callback_query.message, msg)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cfg = get_user_config(chat_id)
    is_gemini_ok = ai_service.is_configured()
    is_subbed = chat_id in subscribers

    status_text = (
        "📊 **ស្ថានភាពប្រព័ន្ធរបស់អ្នក (System Status)**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🎯 វិស័យរបស់អ្នក: **{cfg.get('niche')}**\n"
        f"• ⏱️ រយៈពេលវីដេអូ: **{cfg.get('duration')}**\n"
        f"• ⏰ ម៉ោងផ្ញើស្វ័យប្រវត្ត: **ម៉ោង {cfg.get('daily_time')}**\n"
        f"• 🔔 ស្ថានភាព Subscribe: {'✅ បានបើក' if is_subbed else '❌ មិនទាន់បើក'}\n"
        f"• 🧠 AI Engine: {'🟢 ដំណើរការល្អ' if is_gemini_ok else '🔴 មិនទាន់ដាក់ Key'}\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    await safe_reply(update.message, status_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **បញ្ជីពាក្យបញ្ជាទាំងអស់ (All Commands)**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔹 `/start` ៖ បើកផ្ទាំងដើម និងមើលការកំណត់\n"
        "🔹 `/now` ៖ បង្កើត Script ថ្ងៃនេះភ្លាមៗតាមវិស័យរបស់អ្នក\n"
        "🔹 `/gen <ប្រធានបទ>` ៖ បង្កើត Script តាមប្រធានបទជាក់លាក់\n"
        "🔹 `/setniche <ឈ្មោះវិស័យ>` ៖ ប្តូរវិស័យផ្តោតចម្បងរបស់អ្នក\n"
        "🔹 `/setduration <រយៈពេល>` ៖ ប្តូររយៈពេលវីដេអូ (60s, 2m, 3m, 5m)\n"
        "🔹 `/ideas` ៖ សុំគំនិតប្រធានបទថ្មីៗថ្ងៃនេះ\n"
        "🔹 `/subscribe` ៖ បើកការផ្ញើស្វ័យប្រវត្តរាល់ព្រឹក\n"
        "🔹 `/unsubscribe` ៖ ផ្អាកការផ្ញើប្រចាំថ្ងៃ\n"
        "🔹 `/status` ៖ ពិនិត្យមើលស្ថានភាពនៃការកំណត់របស់អ្នក\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *អ្នកក៏អាចវាយសារជជែកសួរនាំជាភាសាខ្មែរជាមួយខ្ញុំដោយផ្ទាល់បានគ្រប់ពេល!*"
    )
    if update.message:
        await safe_reply(update.message, help_text)
    elif update.callback_query:
        await safe_reply(update.callback_query.message, help_text)

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = update.effective_chat.id

    if data == "btn_now":
        await query.answer()
        await now_command(update, context)
    elif data == "btn_ideas":
        await query.answer()
        await ideas_command(update, context)
    elif data == "btn_guide_niche":
        await query.answer()
        guide = (
            "🎯 **របៀបប្តូរវិស័យផ្តោតចម្បង៖**\n\n"
            "សូមវាយពាក្យ៖ `/setniche [ឈ្មោះវិស័យ]`\n\n"
            "ឧទាហរណ៍៖\n"
            "`/setniche សាលាបង្រៀនធ្វើម្ហូបហាក់ហេង`\n"
            "`/setniche ហាងកាហ្វេ និងភេសជ្ជៈ`\n"
            "`/setniche ស្ថាបត្យកម្ម SketchUp`"
        )
        await safe_reply(query.message, guide)
    elif data == "btn_guide_duration":
        await query.answer()
        guide = (
            "⏱️ **របៀបប្តូររយៈពេលវីដេអូ៖**\n\n"
            "សូមវាយពាក្យ៖ `/setduration [រយៈពេល]`\n\n"
            "ឧទាហរណ៍៖\n"
            "`/setduration 60 វិនាទី`\n"
            "`/setduration 2 នាទី`\n"
            "`/setduration 3 នាទី`\n"
            "`/setduration 5 នាទី`"
        )
        await safe_reply(query.message, guide)
    elif data == "btn_subscribe":
        await subscribe_command(update, context)
    elif data == "btn_unsubscribe":
        await unsubscribe_command(update, context)
    elif data == "btn_help":
        await query.answer()
        await help_command(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return

    # Send typing status
    await update.message.chat.send_action("typing")

    response = await ai_service.chat(user_text)
    await safe_reply(update.message, response)

async def send_daily_content(context: ContextTypes.DEFAULT_TYPE):
    """Job callback to broadcast daily 3WHs content to subscribers."""
    logger.info("Triggering scheduled daily 3WHs content broadcast...")
    if not subscribers:
        logger.info("No subscribers registered for daily broadcast.")
        return

    for chat_id in list(subscribers):
        try:
            cfg = get_user_config(chat_id)
            niche = cfg.get("niche", DEFAULT_NICHE)
            duration = cfg.get("duration", DEFAULT_DURATION)
            content = await ai_service.generate_daily_ideas(niche)
            broadcast_msg = (
                f"☀️ **អរុណសួស្តី! នេះជាមាតិកាវីដេអូ 3WHs សម្រាប់វិស័យ [{niche}] ថ្ងៃនេះ៖**\n\n"
                f"{content}\n\n"
                "💡 *ចង់បាន Script ពេញលេញ? គ្រាន់តែវាយ `/gen <ឈ្មោះប្រធានបទ>` មកកាន់ខ្ញុំ!*"
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=broadcast_msg,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send daily content to {chat_id}: {e}")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("\n❌ កំហុស៖ មិនទាន់មាន TELEGRAM_BOT_TOKEN នៅឡើយទេ។")
        print("👉 សូមបើក file `.env` រួចបញ្ចូល Token របស់អ្នកជាមុនសិន។\n")
        return

    # Start health check server if running on cloud (Render / Railway)
    start_health_check_server()

    # Create Telegram Application
    application = ApplicationBuilder().token(token).build()

    # Register Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("gen", gen_command))
    application.add_handler(CommandHandler("script", gen_command))
    application.add_handler(CommandHandler("now", now_command))
    application.add_handler(CommandHandler("setniche", setniche_command))
    application.add_handler(CommandHandler("setduration", setduration_command))
    application.add_handler(CommandHandler("ideas", ideas_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CommandHandler("status", status_command))

    # Register Callback Query and Message Handlers
    application.add_handler(CallbackQueryHandler(button_callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Setup Daily Job Scheduler
    daily_time_str = os.getenv("DAILY_TIME", "08:00")
    timezone_str = os.getenv("TIMEZONE", "Asia/Phnom_Penh")
    try:
        hour, minute = map(int, daily_time_str.split(":"))
        tz = pytz.timezone(timezone_str)
        scheduled_time = time(hour=hour, minute=minute, tzinfo=tz)

        job_queue = application.job_queue
        if job_queue:
            job_queue.run_daily(send_daily_content, time=scheduled_time)
            logger.info(f"Daily scheduler configured for {daily_time_str} ({timezone_str})")
        else:
            logger.warning("JobQueue not initialized. (Install python-telegram-bot[job-queue])")
    except Exception as e:
        logger.error(f"Failed to schedule daily job: {e}")

    print("\n" + "="*50)
    print("🚀 3WHs Telegram Bot Agent កំពុងដំណើរការ...")
    print("🤖 ចូលទៅកាន់ Telegram ហើយសាកល្បងចុច /start ជាមួយ Bot របស់អ្នក!")
    print("="*50 + "\n")

    application.run_polling()

if __name__ == "__main__":
    main()
