"""
app/handlers/commands.py - Command handlers: /start, /cancel, /help, /ideas, /pace, /status, /subscribe, /unsubscribe.
"""

import math
import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.models import UserKey
from app.navigation import navigation, Screens
from app.keyboards import get_main_menu_keyboard
from app.views import render_welcome, render_help
from app.telegram_io import safe_reply, safe_edit
from script_models import count_khmer_dialogue_units

logger = logging.getLogger(__name__)

def get_user_key(update: Update) -> UserKey:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else chat_id
    return UserKey(chat_id=chat_id, user_id=user_id)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resets screen, cancels any pending generation. If first visit, shows niche selection; otherwise shows main menu."""
    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    task_mgr = context.bot_data["task_mgr"]

    await task_mgr.cancel_request(user_key)
    saved_niche = storage.get_user_niche(user_key)
    target = update.message or (update.callback_query.message if update.callback_query else None)

    if not saved_niche:
        navigation.go_to(user_key, Screens.NICHE_SELECTION)
        from app.views import render_niche_selection
        from app.keyboards import get_niche_selection_keyboard
        msg = render_niche_selection()
        keyboard = get_niche_selection_keyboard()
    else:
        navigation.go_home(user_key)
        settings = storage.get_settings(user_key)
        msg = render_welcome(settings["duration"])
        keyboard = get_main_menu_keyboard()

    if update.callback_query:
        await safe_edit(update.callback_query, msg, reply_markup=keyboard)
    elif target:
        await safe_reply(target, msg, reply_markup=keyboard)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels active generation task and returns to main menu while preserving last successful script."""
    user_key = get_user_key(update)
    storage = context.bot_data.get("storage") if (hasattr(context, "bot_data") and isinstance(context.bot_data, dict)) else None
    if not storage:
        from app.storage import default_storage
        storage = default_storage

    task_mgr = context.bot_data.get("task_mgr") if (hasattr(context, "bot_data") and isinstance(context.bot_data, dict)) else None
    if not task_mgr:
        from app.task_manager import task_manager
        task_mgr = task_manager

    was_active = False
    if hasattr(task_mgr, "cancel_request"):
        import asyncio
        res = task_mgr.cancel_request(user_key)
        if asyncio.iscoroutine(res):
            was_active = await res
        else:
            was_active = bool(res)

    # Legacy context.user_data compatibility
    if hasattr(context, "user_data") and isinstance(context.user_data, dict):
        if "active_task" in context.user_data and context.user_data["active_task"]:
            try:
                context.user_data["active_task"].cancel()
                was_active = True
            except Exception:
                pass
        context.user_data["req_token"] = context.user_data.get("req_token", 0) + 1
        context.user_data["is_processing"] = False
        context.user_data["is_cancelled"] = True

    navigation.go_home(user_key)

    settings = storage.get_settings(user_key)
    status_note = "សំណើកំពុងដំណើរការត្រូវបានបោះបង់!" if was_active else "បានត្រឡប់ទៅកាន់ Menu ដើមវិញ។"
    msg = (
        f"🚫 *{status_note}*\n"
        "_(Script ជោគជ័យចុងក្រោយរបស់អ្នកត្រូវបានរក្សាទុកដដែល)_\n\n"
        + render_welcome(settings["duration"])
    )
    keyboard = get_main_menu_keyboard()
    target = update.message or (update.callback_query.message if update.callback_query else None)
    await safe_reply(target, msg, reply_markup=keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message or update.callback_query.message
    await safe_reply(target, render_help())

async def pace_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Calibrates user speaking pace without calling AI.
    Usage: /pace <seconds> <Khmer sample text>
    Validates finite positive seconds, checks sample length, and avoids silent clamping.
    """
    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    target = update.message or (update.callback_query.message if update.callback_query else None)

    if not context.args or len(context.args) < 2:
        help_pace = (
            "🎙️ *ការវាស់ និងកំណត់ល្បឿននិយាយផ្ទាល់ខ្លួន (Speaking Pace Calibration)*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "សូមអានអត្ថបទគំរូជាភាសាខ្មែរខាងក្រោម ដោយកំណត់ម៉ោង (Timer) នៅលើទូរស័ព្ទរបស់អ្នក រួចផ្ញើចំនួនវិនាទីដែលអ្នកបានអានចប់មកវិញ៖\n\n"
            "📝 *អត្ថបទគំរូសាកល្បង៖*\n"
            "_«សួស្តីអ្នកទាំងអស់គ្នា! ថ្ងៃនេះខ្ញុំមានគន្លឹះពិសេសមួយចង់ចែករំលែក សម្រាប់អ្នកដែលចង់ចាប់ផ្តើមផលិតមាតិកាវីដេអូខ្លីឱ្យទាក់ទាញ និងចំណេញពេលវេលា។»_\n\n"
            "👉 *របៀបវាយបញ្ជា៖*\n"
            "`/pace <ចំនួនវិនាទី> <អត្ថបទដែលអ្នកបានអាន>`\n\n"
            "_ឧទាហរណ៍៖_\n"
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

    current_settings = storage.get_settings(user_key)
    storage.save_settings(user_key, current_settings["duration"], calculated_pace)

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

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    ai = context.bot_data["ai"]

    settings = storage.get_settings(user_key)
    is_subbed = storage.is_subscribed(user_key)
    sub_count = len(storage.get_active_subscribers())
    api_info = ai.get_status_info()

    text = (
        "📊 *ស្ថានភាពប្រព័ន្ធលម្អិត (System Status)*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"• ⏱️ រយៈពេលវីដេអូទូទៅ: *{settings['duration']}*\n"
        f"• 🎙️ ល្បឿននិយាយប៉ាន់ស្មាន: *{settings['pace']:.1f} តួអក្សរ/វិនាទី*\n"
        f"• 🔔 Subscribe ប្រចាំថ្ងៃ: {'✅ បើក (ម៉ោង 08:00)' if is_subbed else '❌ មិនទាន់បើក'}\n"
        f"• 👥 អ្នក Subscribe សរុប: *{sub_count} នាក់*\n"
        f"• 🔑 Gemini API Key: {'✅ បានកំណត់រួចរាល់' if api_info['configured'] else '❌ មិនទាន់កំណត់'}\n"
        f"• ⚙️ AI Engine: *{api_info['sdk']}*\n"
        f"• 🟢 ស្ថានភាព API ចុងក្រោយ: *{api_info['last_status']}*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "ℹ️ _ការផ្សាយប្រចាំថ្ងៃដំណើរការបានលុះត្រាតែ Server ដំណើរការ (Online)_.\n"
        "💡 _ប្រើ /cancel ដើម្បីបោះបង់សំណើពេលណាក៏បាន!_"
    )
    target = update.message or update.callback_query.message
    await safe_reply(target, text)

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    storage.set_subscription(user_key, True)

    msg = (
        "✅ *Subscribe ជោគជ័យ!* 🎉\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Bot នឹងផ្ញើគំនិត Content ថ្មីៗ\n"
        "ជារៀងរាល់ព្រឹក ម៉ោង *08:00* ដោយស្វ័យប្រវត្តិ 🚀"
    )
    target = update.message or update.callback_query.message
    await safe_reply(target, msg)

async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    storage.set_subscription(user_key, False)

    target = update.message or update.callback_query.message
    await safe_reply(target, "🔕 *បានបិទ Subscribe រួចរាល់!*")
