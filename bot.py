"""
bot.py - Application Entry Point for 3WHs Video Script Telegram Bot.

Architecture:
1. Load validated configuration (config.py).
2. Initialize SQLite storage & migrations (app/storage.py).
3. Initialize AI transport & generation service (ai_service.py).
4. Register domain handlers (commands, menu, creation, ideas, scripts, settings, comedy).
5. Register daily scheduler with JobQueue verification (app/jobs.py).
6. Start health check endpoint and begin polling with concurrent_updates(True).
"""

import os
import sys
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import load_config, AppConfig
from app.models import UserKey
from app.storage import Storage
from app.task_manager import task_manager, TaskManager
from app.navigation import navigation, Screens
from app.telegram_io import split_message, safe_reply
from ai_service import AIService
from app.jobs import register_daily_job
from app.services.broadcast import send_daily_broadcast

# Handlers
from app.handlers.commands import (
    get_user_key,
    start_command,
    cancel_command,
    help_command,
    pace_command,
    status_command,
    subscribe_command,
    unsubscribe_command,
)
from app.handlers.menu import handle_menu_callback
from app.handlers.creation import (
    handle_format_callback,
    handle_draft_duration_callback,
    handle_generate_callback,
    handle_retry_callback,
)
from app.handlers.ideas import handle_idea_pick_callback, start_ideas_flow
from app.handlers.scripts import (
    handle_script_action_callback,
    handle_hook_pick_callback,
)
from app.handlers.settings import (
    handle_settings_callback,
    handle_pace_seconds_input,
)
from app.handlers.comedy import handle_comedy_callback

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Default instances for backward compatibility
default_storage = Storage()
default_ai = AIService()

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

def start_health_check_server(port: Optional[int]):
    if not port:
        return
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info(f"Health check server running on port {port}")
    except Exception as e:
        logger.error(f"Health check server error: {e}")

# ─────────────────────────────────────────────
# Text Message Routing by Navigation State
# ─────────────────────────────────────────────
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Routes user text according to active navigation state.
    Does not send user input to free chat while a wizard step is active.
    """
    user_text = update.message.text
    if not user_text:
        return

    user_key = get_user_key(update)
    storage = context.bot_data.get("storage", default_storage) if (hasattr(context, "bot_data") and isinstance(context.bot_data, dict)) else default_storage
    ai = context.bot_data.get("ai", ai_service) if (hasattr(context, "bot_data") and isinstance(context.bot_data, dict)) else ai_service
    task_mgr = context.bot_data.get("task_mgr", task_manager) if (hasattr(context, "bot_data") and isinstance(context.bot_data, dict)) else task_manager
    state = navigation.get_state(user_key)

    # Legacy state compatibility for tests
    if hasattr(context, "user_data") and isinstance(context.user_data, dict) and context.user_data.get("state") == "awaiting_topic":
        content_type = context.user_data.get("content_type", "3whs")
        target_ai = ai_service if hasattr(ai_service, "generate_content_by_type") else ai
        import asyncio
        call_res = target_ai.generate_content_by_type(content_type, user_text)
        res = await call_res if asyncio.iscoroutine(call_res) else call_res
        if getattr(res, "success", False) and getattr(res, "plan", None):
            context.user_data["last_script"] = res.formatted_text
            context.user_data["last_script_plan"] = res.plan
            await update.message.reply_text("រួចរាល់!\n" + res.formatted_text)
        else:
            err = getattr(res, "error_message", None) or "កំហុសបច្ចេកទេស"
            await update.message.reply_text(f"មិនទាន់ជោគជ័យ៖ {err}")
        return

    # 0. State: Entering Custom Niche
    if state.current_screen == Screens.NICHE_CUSTOM_INPUT:
        custom_niche = user_text.strip()
        if custom_niche:
            storage.save_user_niche(user_key, custom_niche)
            storage.clear_incompatible_drafts(user_key)

            settings = storage.get_settings(user_key)
            from script_models import parse_duration_seconds
            dur_s = parse_duration_seconds(settings["duration"])

            draft = Draft(
                id=f"d_{uuid.uuid4().hex[:8]}",
                revision=1,
                format_id="3whs",
                topic="",
                duration_seconds=dur_s,
                audience="",
                current_step="format",
                owner=user_key,
                niche=custom_niche,
            )
            storage.save_draft(user_key, draft)
            navigation.go_to(user_key, Screens.FORMAT_SELECTION, draft_id=draft.id)

            from app.views import render_format_selection
            from app.keyboards import get_format_selection_keyboard
            from app.telegram_io import safe_reply

            notice = (
                f"✅ *បានកំណត់វិស័យផ្ទាល់ខ្លួន៖* `{custom_niche}`\n"
                "_(សេចក្ដីព្រាងចាស់ដែលមិនត្រូវគ្នាត្រូវបានជម្រះ ប៉ុន្តែ Script ជោគជ័យត្រូវបានរក្សាទុកដដែល)_\n\n"
            )
            msg = notice + render_format_selection(custom_niche)
            keyboard = get_format_selection_keyboard(draft)
            await safe_reply(update.message, msg, reply_markup=keyboard)
            return

    # 1. State: Entering Topic for Draft (Flexible at Topic Input, Topic/Ideas, or Format Selection)
    elif (state.current_screen in (Screens.TOPIC_INPUT, Screens.TOPIC_OR_IDEAS, Screens.FORMAT_SELECTION, Screens.IDEA_RESULTS)) and state.draft_id:
        draft = storage.get_draft(state.draft_id)
        if draft:
            draft.topic = user_text.strip()
            draft.audience = user_text.strip()
            if not draft.niche:
                draft.niche = storage.get_user_niche(user_key) or "ទូទៅ"
            draft.revision += 1
            draft.current_step = "review"
            storage.save_draft(user_key, draft)
            navigation.go_to(user_key, Screens.DRAFT_REVIEW, draft_id=draft.id)

            settings = storage.get_settings(user_key)
            from app.views import render_review
            from app.keyboards import get_review_keyboard
            from app.telegram_io import safe_reply

            msg = render_review(draft, settings["pace"])
            keyboard = get_review_keyboard(draft)
            await safe_reply(update.message, msg, reply_markup=keyboard)
            return

    # 2. State: Entering Pace Seconds
    elif state.current_screen == Screens.PACE_SECONDS:
        await handle_pace_seconds_input(update, context, user_text)
        return

    # 3. Default: Free-text AI Chat Coach
    token = None
    if hasattr(task_mgr, "start_request"):
        import asyncio
        res = task_mgr.start_request(user_key, "chat")
        token = await res if asyncio.iscoroutine(res) else res
    if token is None:
        await update.message.reply_text("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!")
        return

    try:
        await update.message.chat.send_action("typing")
        response = await ai.chat(user_text)
        if not hasattr(task_mgr, "is_current_request") or task_mgr.is_current_request(user_key, token):
            await safe_reply(update.message, response)
    finally:
        if hasattr(task_mgr, "finish_request"):
            import asyncio
            fin_res = task_mgr.finish_request(user_key, token)
            if asyncio.iscoroutine(fin_res):
                await fin_res

# ─────────────────────────────────────────────
# Callback Query Dispatcher
# ─────────────────────────────────────────────
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Central dispatcher for all compact callback schemes with exception safety."""
    query = update.callback_query
    data = query.data or ""

    try:
        if data.startswith("m:") or data.startswith("n:"):
            await handle_menu_callback(update, context)
        elif data.startswith("f:"):
            await handle_format_callback(update, context)
        elif data.startswith("d:"):
            await handle_draft_duration_callback(update, context)
        elif data.startswith("g:"):
            await handle_generate_callback(update, context)
        elif data.startswith("r:"):
            await handle_retry_callback(update, context)
        elif data.startswith("i:"):
            await handle_idea_pick_callback(update, context)
        elif data.startswith("s:"):
            await handle_script_action_callback(update, context)
        elif data.startswith("h:"):
            await handle_hook_pick_callback(update, context)
        elif data.startswith("c:"):
            await handle_comedy_callback(update, context)
        elif data.startswith("set:"):
            await handle_settings_callback(update, context)
        elif data.startswith("x:"):
            await cancel_command(update, context)
        elif data.startswith("refine:"):
            # Legacy callback handler for tests
            action = data.split(":")[1]
            ai = context.bot_data.get("ai", default_ai) if (hasattr(context, "bot_data") and isinstance(context.bot_data, dict)) else default_ai
            last_plan = context.user_data.get("last_script_plan") if hasattr(context, "user_data") else None
            if action == "shorten":
                res = await ai.refine_shorten(last_plan)
            elif action == "regen":
                res = await ai.refine_regenerate(last_plan)
            else:
                res = None

            if res and getattr(res, "success", False) and getattr(res, "plan", None):
                if hasattr(context, "user_data"):
                    context.user_data["last_script"] = res.formatted_text
                    context.user_data["last_script_plan"] = res.plan
                await query.message.reply_text("រួចរាល់!\n" + res.formatted_text)
            else:
                err = getattr(res, "error_message", None) or "កំហុសបច្ចេកទេស"
                await query.message.reply_text(f"មិនទាន់ជោគជ័យ៖ {err}")
        else:
            await query.answer("សំណើមិនត្រឹមត្រូវឡើយ!", show_alert=True)
    except Exception as e:
        logger.error(f"Error handling callback {data}: {e}", exc_info=True)
        try:
            await query.answer("⚠️ មានបញ្ហាបច្ចេកទេសមួយភ្លែត។ សូមសាកល្បងម្ដងទៀត!", show_alert=True)
        except Exception:
            pass

# ─────────────────────────────────────────────
# Backward Compatibility Wrappers
# ─────────────────────────────────────────────
def get_user_duration(chat_id: int) -> str:
    settings = default_storage.get_settings(UserKey(chat_id, chat_id))
    return settings["duration"]

def set_user_duration(chat_id: int, duration: str):
    settings = default_storage.get_settings(UserKey(chat_id, chat_id))
    default_storage.save_settings(UserKey(chat_id, chat_id), duration, settings["pace"])

def get_user_pace(chat_id: int) -> float:
    settings = default_storage.get_settings(UserKey(chat_id, chat_id))
    return float(settings["pace"])

def set_user_pace(chat_id: int, pace: float):
    settings = default_storage.get_settings(UserKey(chat_id, chat_id))
    default_storage.save_settings(UserKey(chat_id, chat_id), settings["duration"], pace)

def is_error_response(text: str) -> bool:
    if not text:
        return True
    s = text.strip()
    return s.startswith("⚠️") or s.startswith("❌") or "Error:" in s

async def send_daily_content(context: ContextTypes.DEFAULT_TYPE):
    storage = context.bot_data.get("storage", default_storage) if (hasattr(context, "bot_data") and isinstance(context.bot_data, dict)) else default_storage
    ai = context.bot_data.get("ai", default_ai) if (hasattr(context, "bot_data") and isinstance(context.bot_data, dict)) else default_ai
    await send_daily_broadcast(context.bot, storage, ai)

# Emulate subscribers set/dict for legacy tests
class SubscribersProxy(set):
    def add(self, item):
        super().add(item)
        default_storage.set_subscription(UserKey(item, item), True)

    def remove(self, item):
        if item in self:
            super().remove(item)
        default_storage.set_subscription(UserKey(item, item), False)

    def __contains__(self, item):
        return default_storage.is_subscribed(UserKey(item, item))

    def __len__(self):
        return len(default_storage.get_active_subscribers())

    def __iter__(self):
        return iter([sub.chat_id for sub in default_storage.get_active_subscribers()])

subscribers = SubscribersProxy()
user_settings = {}
ai_service = default_ai
handle_message = handle_text_message
button_callback_handler = handle_callback_query

def acquire_user_request(context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    if not hasattr(context, "user_data") or not isinstance(context.user_data, dict):
        return None
    if context.user_data.get("is_processing", False):
        return None
    token = context.user_data.get("req_token", 0) + 1
    context.user_data["req_token"] = token
    context.user_data["is_processing"] = True
    context.user_data["is_cancelled"] = False
    return token

def release_user_request(context: ContextTypes.DEFAULT_TYPE, token: int):
    if hasattr(context, "user_data") and isinstance(context.user_data, dict):
        if context.user_data.get("req_token") == token:
            context.user_data["is_processing"] = False

def is_request_current(context: ContextTypes.DEFAULT_TYPE, token: int) -> bool:
    if hasattr(context, "user_data") and isinstance(context.user_data, dict):
        return (
            context.user_data.get("req_token") == token
            and not context.user_data.get("is_cancelled", False)
        )
    user_key = context.user_data.get("user_key") if hasattr(context, "user_data") else None
    if user_key:
        return task_manager.is_current_request(user_key, token)
    return False

async def ideas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = " ".join(context.args).strip() if (context.args and len(context.args) > 0) else "ទូទៅ"
    await start_ideas_flow(update, context, cat)

# ─────────────────────────────────────────────
# Main Application Builder
# ─────────────────────────────────────────────
def main():
    config = load_config()
    if not config.telegram_bot_token:
        print("\nERROR: TELEGRAM_BOT_TOKEN not set in .env\n")
        return

    start_health_check_server(config.port)

    # Initialize storage and AI service
    storage = Storage(db_path=config.db_path)
    ai = AIService()

    # Build Telegram application with concurrent_updates(True)
    application = (
        ApplicationBuilder()
        .token(config.telegram_bot_token)
        .concurrent_updates(True)
        .build()
    )

    if application.job_queue is None:
        logger.error(
            "JobQueue is NOT available! Install python-telegram-bot[job-queue] to enable daily broadcasts. Daily broadcasts will be disabled."
        )

    # Store shared services in bot_data
    application.bot_data["storage"] = storage
    application.bot_data["ai"] = ai
    application.bot_data["task_mgr"] = task_manager
    application.bot_data["config"] = config

    # Specific command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ideas", ideas_command))
    application.add_handler(CommandHandler("pace", pace_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))

    # Compact Callback Query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # State-aware Text Message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Daily scheduler registration
    register_daily_job(
        application=application,
        storage=storage,
        ai=ai,
        daily_time_str=config.daily_time,
        timezone_str=config.timezone,
    )

    print("\n" + "=" * 50)
    print("3WHs Telegram Bot Agent - Running with Clean Architecture...")
    print("Go to Telegram and press /start !")
    print("=" * 50 + "\n")

    application.run_polling()

if __name__ == "__main__":
    main()
