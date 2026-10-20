"""
app/handlers/settings.py - Button-based Settings: Default Duration, Pace Calibration, Subscription Toggle, System Status.
"""

import math
import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.models import UserKey
from app.navigation import navigation, Screens
from app.callbacks import decode_callback
from app.keyboards import (
    get_settings_keyboard,
    get_default_duration_keyboard,
    get_back_home_keyboard,
)
from app.views import (
    render_settings,
    render_pace_sample_instruction,
)
from app.handlers.commands import get_user_key, status_command
from script_models import count_khmer_dialogue_units

logger = logging.getLogger(__name__)

FIXED_KHMER_PACE_SAMPLE = (
    "សួស្តីអ្នកទាំងអស់គ្នា! ថ្ងៃនេះខ្ញុំមានគន្លឹះពិសេសមួយចង់ចែករំលែក សម្រាប់អ្នកដែលចង់ចាប់ផ្តើមផលិតមាតិកាវីដេអូខ្លីឱ្យទាក់ទាញ និងចំណេញពេលវេលា។"
)

async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles set:<action> callbacks."""
    query = update.callback_query
    await query.answer()

    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    decoded = decode_callback(query.data)

    action = decoded.action

    # ── Duration Submenu ──────────────────────
    if action == "dur_menu":
        navigation.go_to(user_key, Screens.DEFAULT_DURATION)
        settings = storage.get_settings(user_key)
        msg = (
            "⏱️ *កំណត់រយៈពេលវីដេអូទូទៅ (Default Duration)*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"• រយៈពេលបច្ចុប្បន្ន៖ *{settings['duration']}*\n\n"
            "_សូមជ្រើសរើសរយៈពេលដែលអ្នកចង់កំណត់ជា Default ខាងក្រោម៖_"
        )
        keyboard = get_default_duration_keyboard(settings["duration"])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── Set Duration ──────────────────────────
    elif action == "dur" or action.startswith("dur:"):
        dur = decoded.extra if decoded.extra else (action.split(":", 1)[1] if ":" in action else "60 វិនាទី")
        settings = storage.get_settings(user_key)
        storage.save_settings(user_key, dur, settings["pace"])
        navigation.go_to(user_key, Screens.SETTINGS)

        is_subbed = storage.is_subscribed(user_key)
        msg = f"✅ *បានកំណត់រយៈពេល {dur} ជាផ្លូវការ!*\n\n" + render_settings(dur, settings["pace"], is_subbed)
        keyboard = get_settings_keyboard(dur, is_subbed)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── Pace Calibration Flow ─────────────────
    elif action == "pace":
        navigation.go_to(user_key, Screens.PACE_SECONDS)
        msg = render_pace_sample_instruction(FIXED_KHMER_PACE_SAMPLE)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_back_home_keyboard())

    # ── Subscription Toggle ───────────────────
    elif action == "sub_toggle":
        is_subbed = storage.is_subscribed(user_key)
        new_status = not is_subbed
        storage.set_subscription(user_key, new_status)

        settings = storage.get_settings(user_key)
        status_note = "✅ *បានបើកទទួលគំនិតប្រចាំថ្ងៃ (08:00)!*" if new_status else "🔕 *បានបិទការទទួលគំនិតប្រចាំថ្ងៃ!*"
        msg = f"{status_note}\n\n" + render_settings(settings["duration"], settings["pace"], new_status)
        keyboard = get_settings_keyboard(settings["duration"], new_status)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── System Status ─────────────────────────
    elif action == "status":
        await status_command(update, context)

async def handle_pace_seconds_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    """Processes seconds text input when user is in Screens.PACE_SECONDS screen."""
    user_key = get_user_key(update)
    storage = context.bot_data["storage"]

    try:
        seconds = float(user_text.strip())
        if not math.isfinite(seconds) or math.isnan(seconds):
            await update.message.reply_text("⚠️ ចំនួនវិនាទីមិនត្រឹមត្រូវឡើយ (NaN ឬ Infinity)។ សូមវាយតែលេខវិនាទី ឧទាហរណ៍៖ `12`")
            return
        if seconds < 2.0 or seconds > 300.0:
            await update.message.reply_text("⚠️ សូមបញ្ចូលចំនួនវិនាទីជាក់ស្តែងចន្លោះពី 2 ដល់ 300 វិនាទី។")
            return
    except ValueError:
        await update.message.reply_text("⚠️ សូមបញ្ចូលតែលេខវិនាទីសុទ្ធ (Numbers only)។ ឧទាហរណ៍៖ `12.5` ឬ `15`")
        return

    units = count_khmer_dialogue_units(FIXED_KHMER_PACE_SAMPLE)
    calculated_pace = round(units / seconds, 2)

    if calculated_pace < 3.0:
        await update.message.reply_text(
            f"⚠️ ល្បឿនគណនាបានយឺតខ្លាំងខុសធម្មតា ({calculated_pace:.1f} តួអក្សរ/s)។ "
            "សូមសាកល្បងអានម្ដងទៀតដោយប្រើល្បឿនសន្ទនាធម្មតា (conversational pace)។"
        )
        return
    if calculated_pace > 25.0:
        await update.message.reply_text(
            f"⚠️ ល្បឿនគណនាបានលឿនខ្លាំងខុសធម្មតា ({calculated_pace:.1f} តួអក្សរ/s)។ "
            "សូមពិនិត្យមើលនាឡិកាកំណត់ម៉ោងរបស់អ្នកឡើងវិញ។"
        )
        return

    settings = storage.get_settings(user_key)
    storage.save_settings(user_key, settings["duration"], calculated_pace)
    navigation.go_to(user_key, Screens.SETTINGS)

    is_subbed = storage.is_subscribed(user_key)
    msg = (
        "✅ *បានកំណត់ល្បឿននិយាយផ្ទាល់ខ្លួនជោគជ័យ!* 🎉\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"• ⏱️ រយៈពេលអាន៖ *{seconds:.1f} វិនាទី*\n"
        f"• 📏 ចំនួនតួអក្សរគំរូរាប់បាន៖ *{units} តួអក្សរ*\n"
        f"• 🎙️ ល្បឿនគណនាជាក់ស្តែង៖ *{calculated_pace:.1f} តួអក្សរ/វិនាទី*\n\n"
        "💡 _ចំណាំ៖ រយៈពេលនិយាយក្នុង Script គឺសម្រាប់តែការប៉ាន់ស្មានប្រហាក់ប្រហែលប៉ុណ្ណោះ។_\n\n"
        + render_settings(settings["duration"], calculated_pace, is_subbed)
    )
    keyboard = get_settings_keyboard(settings["duration"], is_subbed)
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)
