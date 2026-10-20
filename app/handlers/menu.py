"""
app/handlers/menu.py - Main Menu Routing and Navigation (Back/Home) Handling.
"""

import uuid
import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.models import UserKey, Draft
from app.navigation import navigation, Screens
from app.callbacks import decode_callback
from app.keyboards import (
    get_main_menu_keyboard,
    get_format_selection_keyboard,
    get_settings_keyboard,
    get_script_actions_keyboard,
    get_review_keyboard,
    get_comedy_styles_keyboard,
    get_back_home_keyboard,
)
from app.views import (
    render_welcome,
    render_format_selection,
    render_settings,
    render_script_summary,
    render_review,
    render_help,
)
from app.handlers.commands import get_user_key

logger = logging.getLogger(__name__)

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles m:<action> and n:<action> callbacks."""
    query = update.callback_query
    await query.answer()

    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    decoded = decode_callback(query.data)

    action = decoded.action

    # ── HOME ──────────────────────────────────
    if decoded.prefix == "n" and action == "home":
        navigation.go_home(user_key)
        settings = storage.get_settings(user_key)
        msg = render_welcome(settings["duration"])
        keyboard = get_main_menu_keyboard()
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        return

    # ── BACK ──────────────────────────────────
    if decoded.prefix == "n" and action == "back":
        prev_screen, state = navigation.go_back(user_key)
        await render_current_screen(query, user_key, prev_screen, state, storage)
        return

    # ── MENU: CREATE SCRIPT ───────────────────
    if action == "create":
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
        )
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.FORMAT_SELECTION, draft_id=draft.id)

        msg = render_format_selection()
        keyboard = get_format_selection_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── MENU: COMEDY ──────────────────────────
    elif action == "comedy":
        settings = storage.get_settings(user_key)
        from script_models import parse_duration_seconds
        dur_s = parse_duration_seconds(settings["duration"])

        draft = Draft(
            id=f"d_{uuid.uuid4().hex[:8]}",
            revision=1,
            format_id="comedy",
            topic="",
            duration_seconds=dur_s,
            audience="",
            comedy_style="everyday",
            actor_count=1,
            current_step="comedy_style",
        )
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.COMEDY_STYLE, draft_id=draft.id)

        msg = (
            "😂 *បង្កើត Script វីដេអូកំប្លែងខ្លី (Short Comedy Video)*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "សូមជ្រើសរើសស្ទីលកំប្លែងដែលអ្នកចង់ផលិតខាងក្រោម៖"
        )
        keyboard = get_comedy_styles_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── MENU: IDEAS ───────────────────────────
    elif action == "ideas":
        from app.handlers.ideas import start_ideas_flow
        await start_ideas_flow(update, context, "ទូទៅ")

    # ── MENU: LAST SCRIPT ─────────────────────
    elif action == "last":
        script = storage.get_last_successful_script(user_key)
        if not script:
            settings = storage.get_settings(user_key)
            msg = (
                "ℹ️ *មិនទាន់មាន Script ដែលជោគជ័យនៅឡើយទេ*\n\n"
                "សូមចុច **[🎬 បង្កើត Script]** ឬ **[😂 បង្កើតកំប្លែង]** ដើម្បីចាប់ផ្តើមផលិត Script ដំបូងរបស់អ្នក!"
            )
            keyboard = get_main_menu_keyboard()
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
            return

        navigation.go_to(user_key, Screens.SCRIPT_SUMMARY, script_id=script.id, script_version=script.version)
        settings = storage.get_settings(user_key)
        msg = render_script_summary(script, settings["pace"])
        keyboard = get_script_actions_keyboard(script)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── MENU: SETTINGS ────────────────────────
    elif action == "settings":
        navigation.go_to(user_key, Screens.SETTINGS)
        settings = storage.get_settings(user_key)
        is_subbed = storage.is_subscribed(user_key)
        msg = render_settings(settings["duration"], settings["pace"], is_subbed)
        keyboard = get_settings_keyboard(settings["duration"], is_subbed)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── MENU: HELP ────────────────────────────
    elif action == "help":
        navigation.go_to(user_key, Screens.HELP)
        msg = render_help()
        keyboard = get_back_home_keyboard()
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

async def render_current_screen(query, user_key: UserKey, screen: str, state, storage):
    """Renders the screen restored by Back action."""
    settings = storage.get_settings(user_key)

    if screen == Screens.HOME:
        msg = render_welcome(settings["duration"])
        keyboard = get_main_menu_keyboard()
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif screen == Screens.FORMAT_SELECTION:
        draft = storage.get_draft(state.draft_id) if state.draft_id else None
        if not draft:
            return await render_current_screen(query, user_key, Screens.HOME, state, storage)
        msg = render_format_selection()
        keyboard = get_format_selection_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif screen == Screens.DRAFT_REVIEW:
        draft = storage.get_draft(state.draft_id) if state.draft_id else None
        if not draft:
            return await render_current_screen(query, user_key, Screens.HOME, state, storage)
        msg = render_review(draft, settings["pace"])
        keyboard = get_review_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif screen in (Screens.SCRIPT_SUMMARY, Screens.SCRIPT_READ, Screens.SCRIPT_SHOTS, Screens.SCRIPT_CAPTION):
        script = storage.get_script(state.selected_script_id, state.selected_script_version) if (state.selected_script_id and state.selected_script_version) else storage.get_last_successful_script(user_key)
        if not script:
            return await render_current_screen(query, user_key, Screens.HOME, state, storage)
        msg = render_script_summary(script, settings["pace"])
        keyboard = get_script_actions_keyboard(script)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif screen == Screens.SETTINGS:
        is_subbed = storage.is_subscribed(user_key)
        msg = render_settings(settings["duration"], settings["pace"], is_subbed)
        keyboard = get_settings_keyboard(settings["duration"], is_subbed)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    else:
        # Fallback to HOME
        msg = render_welcome(settings["duration"])
        keyboard = get_main_menu_keyboard()
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
