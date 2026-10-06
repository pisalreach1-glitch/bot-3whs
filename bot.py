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

# Database for subscribed users (JSON file)
SUBSCRIBERS_FILE = "subscribers.json"

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
        # Find newline to split nicely
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
    # If there are additional chunks, send them as subsequent messages
    for extra_chunk in chunks[1:]:
        try:
            await status_msg.reply_text(extra_chunk, parse_mode="Markdown")
        except Exception:
            await status_msg.reply_text(extra_chunk)

def get_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💡 គំនិតប្រធានបទថ្ងៃនេះ", callback_data="btn_ideas"),
            InlineKeyboardButton("🎬 របៀបបង្កើត Script", callback_data="btn_how_to_script")
        ],
        [
            InlineKeyboardButton("🔔 Subscribe ទទួលរាល់ព្រឹក", callback_data="btn_subscribe"),
            InlineKeyboardButton("🔕 បិទការផ្ញើប្រចាំថ្ងៃ", callback_data="btn_unsubscribe")
        ],
        [
            InlineKeyboardButton("ℹ️ ជំនួយ & ពាក្យបញ្ជា", callback_data="btn_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name if update.effective_user else "អ្នកបង្កើតមាតិកា"
    welcome_text = (
        f"👋 **សួស្តី {user_name}! ខ្ញុំជា 3WHs Video Content Agent** 🎬✨\n\n"
        "ខ្ញុំនៅទីនេះដើម្បីជួយអ្នកផលិត Script វីដេអូខ្លី (TikTok / Reels / Shorts) "
        "និងវីដេអូវែង តាមរូបមន្ត **3WHs (What, Why, Who, How)** ឱ្យទាក់ទាញ និងងាយស្រួលធ្វើតាមបំផុត។\n\n"
        "📌 **របៀបប្រើប្រាស់រហ័ស៖**\n"
        "• វាយ `/script <ប្រធានបទ>` (ឧ. `/script របៀបគ្រប់គ្រងលុយ`)\n"
        "• វាយ `/ideas` ដើម្បីសុំគំនិតប្រធានបទថ្មីៗថ្ងៃនេះ\n"
        "• ឬគ្រាន់តែ**ផ្ញើសារធម្មតា**មកខ្ញុំដើម្បីជជែក ឬពិភាក្សាគំនិតមាតិកា!\n\n"
        "👇 សូមជ្រើសរើសជម្រើសខាងក្រោម៖"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **បញ្ជីពាក្យបញ្ជា (Commands List)**\n\n"
        "1. `/start` - បើកផ្ទាំងដើម\n"
        "2. `/script <ប្រធានបទ>` - បង្កើត Script វីដេអូ 3WHs ពេញលេញភ្លាមៗ\n"
        "3. `/ideas` - ទទួលបានគំនិតប្រធានបទ 3WHs កំពុងពេញនិយម\n"
        "4. `/subscribe` - ចុះឈ្មោះទទួល Script & គំនិតមាតិកាជារៀងរាល់ព្រឹក\n"
        "5. `/unsubscribe` - ឈប់ទទួលសារប្រចាំថ្ងៃស្វ័យប្រវត្តិ\n"
        "6. `/status` - ពិនិត្យមើលស្ថានភាពនៃការតភ្ជាប់ Bot\n\n"
        "💡 *អ្នកក៏អាចវាយសារជជែកជាភាសាខ្មែរជាមួយខ្ញុំដោយផ្ទាល់បានគ្រប់ពេល!*"
    )
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(help_text, parse_mode="Markdown")

async def script_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        guide_text = (
            "⚠️ **សូមបញ្ជាក់ប្រធានបទ និងប្រវែងវីដេអូដែលអ្នកចង់ធ្វើ!**\n\n"
            "📌 **របៀបសរសេរ៖**\n"
            "• វីដេអូខ្លី (Shorts/Reels 60s): `/script <ប្រធានបទ> 60s`\n"
            "• វីដេអូមធ្យម (2-3 នាទី): `/script <ប្រធានបទ> 3mn`\n"
            "• វីដេអូវែង (5-10 នាទី): `/script <ប្រធានបទ> 5mn`\n\n"
            "💡 **ឧទាហរណ៍៖**\n"
            "`/script របៀបភ្ញាក់ពីព្រលឹមដោយមិនងងុយ 60s`\n"
            "`/script យុទ្ធសាស្ត្រលក់អនឡាញ 3mn`\n"
            "`/script មូលដ្ឋានគ្រឹះក្នុងការវិនិយោគ 10mn`"
        )
        await safe_reply(update.message, guide_text)
        return

    full_text = " ".join(context.args)
    duration = "60s (Short Video)"

    # Check for duration keywords at the end or within text
    lower_text = full_text.lower()
    if any(k in lower_text for k in ["10mn", "10 នាទី", "10 min", "10 mins", "10 minute", "10 minutes"]):
        duration = "10 នាទី (Long YouTube Video)"
    elif any(k in lower_text for k in ["5mn", "5 នាទី", "5 min", "5 mins", "5 minute", "5 minutes"]):
        duration = "5 នាទី (Long Video)"
    elif any(k in lower_text for k in ["3mn", "3 នាទី", "3 min", "3 mins", "3 minute", "3 minutes"]):
        duration = "3 នាទី (Medium Explainer Video)"
    elif any(k in lower_text for k in ["2mn", "2 នាទី", "2 min", "2 mins", "2 minute", "2 minutes"]):
        duration = "2 នាទី (Medium Video)"
    elif any(k in lower_text for k in ["30s", "30 វិនាទី", "45s", "60s", "1mn", "1 នាទី", "ខ្លី"]):
        duration = "30s - 60s (Short Video - TikTok/Reels)"

    status_msg = await update.message.reply_text(f"⏳ កំពុងរៀបចំ Script 3WHs ប្រវែង [{duration}] ជូនអ្នក...")

    response = await ai_service.generate_script(full_text, duration)
    await safe_edit(status_msg, response)

async def ideas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = " ".join(context.args) if context.args else "ទូទៅ / អាជីវកម្ម / បច្ចេកវិទ្យា / ការអភិវឌ្ឍខ្លួន"
    
    if update.message:
        status_msg = await update.message.reply_text("💡 កំពុងស្វែងរកគំនិត 3WHs ល្អៗសម្រាប់ថ្ងៃនេះ...")
    else:
        status_msg = await update.callback_query.message.reply_text("💡 កំពុងស្វែងរកគំនិត 3WHs ល្អៗសម្រាប់ថ្ងៃនេះ...")

    response = await ai_service.generate_daily_ideas(category)
    await safe_edit(status_msg, response)

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    save_subscribers(subscribers)
    msg = (
        "✅ **បានចុះឈ្មោះជោគជ័យ!**\n\n"
        "ខ្ញុំនឹងផ្ញើគំនិតមាតិកា និង Script 3WHs មកកាន់អ្នកជារៀងរាល់ថ្ងៃនៅម៉ោងកំណត់។ 🚀"
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
        msg = "🔕 អ្នកបានផ្អាកការទទួលមាតិកាប្រចាំថ្ងៃដោយជោគជ័យ។"
    else:
        msg = "ℹ️ អ្នកមិនទាន់បាន Subscribe នៅឡើយទេ។"

    if update.message:
        await safe_reply(update.message, msg)
    elif update.callback_query:
        await update.callback_query.answer()
        await safe_reply(update.callback_query.message, msg)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_gemini_ok = ai_service.is_configured()
    chat_id = update.effective_chat.id
    is_subbed = chat_id in subscribers
    daily_time = os.getenv("DAILY_TIME", "08:00")
    timezone = os.getenv("TIMEZONE", "Asia/Phnom_Penh")

    status_text = (
        "📊 **ស្ថានភាព Bot (System Status)**\n\n"
        f"• AI Service (Gemini): {'🟢 ដំណើរការ' if is_gemini_ok else '🔴 មិនទាន់ដាក់ API Key'}\n"
        f"• Daily Schedule: ⏰ ម៉ោង {daily_time} ({timezone})\n"
        f"• ចំនួនអ្នក Subscribe សរុប: {len(subscribers)} នាក់\n"
        f"• គណនីរបស់អ្នក: {'✅ បាន Subscribe រួចរាល់' if is_subbed else '❌ មិនទាន់បាន Subscribe'}\n"
    )
    await safe_reply(update.message, status_text)

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "btn_ideas":
        await query.answer()
        await ideas_command(update, context)
    elif data == "btn_how_to_script":
        await query.answer()
        guide = (
            "🎬 **របៀបបង្កើត Script វីដេអូ 3WHs៖**\n\n"
            "គ្រាន់តែវាយពាក្យ `/script` បន្ទាប់មកដាក់ប្រធានបទរបស់អ្នក។\n\n"
            "ឧទាហរណ៍៖\n"
            "`/script ទម្លាប់ ៥ យ៉ាងជួយឱ្យជោគជ័យ`\n"
            "`/script ហេតុអ្វីបានជាត្រូវបង្កើត Personal Brand?`\n"
            "`/script វិធីសាស្រ្តសន្សំលុយសម្រាប់យុវជន`"
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

    # If message looks like a direct topic request, provide full script or chat response
    response = await ai_service.chat(user_text)
    await safe_reply(update.message, response)

async def send_daily_content(context: ContextTypes.DEFAULT_TYPE):
    """Job callback to broadcast daily 3WHs content to subscribers."""
    logger.info("Triggering scheduled daily 3WHs content broadcast...")
    if not subscribers:
        logger.info("No subscribers registered for daily broadcast.")
        return

    content = await ai_service.generate_daily_ideas()
    broadcast_msg = (
        "☀️ **អរុណសួស្តី! នេះជាមាតិកាវីដេអូ 3WHs សម្រាប់ថ្ងៃនេះ៖**\n\n"
        f"{content}\n\n"
        "💡 *ចង់បាន Script លម្អិតសម្រាប់ប្រធានបទណាមួយខាងលើ? គ្រាន់តែវាយ `/script <ឈ្មោះប្រធានបទ>` មកកាន់ខ្ញុំ!*"
    )

    for chat_id in list(subscribers):
        try:
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
    application.add_handler(CommandHandler("script", script_command))
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
