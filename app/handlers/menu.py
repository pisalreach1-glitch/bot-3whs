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
    get_niche_selection_keyboard,
    get_format_selection_keyboard,
    get_topic_or_ideas_keyboard,
    get_settings_keyboard,
    get_script_actions_keyboard,
    get_review_keyboard,
    get_comedy_styles_keyboard,
    get_back_home_keyboard,
    get_draft_duration_keyboard,
)
from app.views import (
    render_welcome,
    render_niche_selection,
    render_format_selection,
    render_topic_or_ideas,
    render_settings,
    render_script_summary,
    render_review,
    render_help,
    render_topic_prompt,
)
from app.handlers.commands import get_user_key

logger = logging.getLogger(__name__)

NICHE_MAP = {
    "food": "🍜 Food / Cooking",
    "coffee": "☕️ Coffee / Beverages",
    "sales": "🛍 Sales / Online Business",
    "education": "📚 Education / Skills",
    "tech": "📱 Technology / AI",
    "selfdev": "🌱 Personal Development",
}

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles m:<action> and n:<action> callbacks."""
    query = update.callback_query
    await query.answer()

    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    decoded = decode_callback(query.data)

    action = decoded.action

    # ── HOME ──────────────────────────────────
    if (decoded.prefix in ("n", "m")) and action == "home":
        task_mgr = context.bot_data.get("task_mgr")
        if task_mgr:
            await task_mgr.cancel_request(user_key)
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

    # ── MENU: CHANGE NICHE ────────────────────
    if action == "change_niche":
        navigation.go_to(user_key, Screens.NICHE_SELECTION)
        msg = render_niche_selection()
        keyboard = get_niche_selection_keyboard()
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        return

    # ── MENU: NICHE PICK ──────────────────────
    elif action == "niche":
        niche_token = decoded.token
        if niche_token == "custom":
            navigation.go_to(user_key, Screens.NICHE_CUSTOM_INPUT)
            msg = (
                "✏️ *សូមវាយបញ្ចូលវិស័យមាតិកាផ្ទាល់ខ្លួនរបស់អ្នក (Custom Niche)*\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "សូមវាយឈ្មោះវិស័យមាតិកាដែលអ្នកចង់ផលិតរួចផ្ញើមកកាន់ Bot៖\n\n"
                "_ឧទាហរណ៍៖ Khmer cooking, ទេសចរណ៍ និងដើរលេង, ហិរញ្ញវត្ថុផ្ទាល់ខ្លួន, សុខភាព..._\n\n"
                "💡 _អ្នកអាចចុច ⬅️ ត្រឡប់ក្រោយ ឬ /cancel ដើម្បីបោះបង់!_"
            )
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_back_home_keyboard())
            return

        chosen_niche = NICHE_MAP.get(niche_token, niche_token)
        storage.save_user_niche(user_key, chosen_niche)
        storage.clear_incompatible_drafts(user_key)

        from script_models import parse_duration_seconds
        settings = storage.get_settings(user_key)
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
            niche=chosen_niche,
        )
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.FORMAT_SELECTION, draft_id=draft.id)

        notice_text = (
            f"✅ *បានកំណត់វិស័យ៖* `{chosen_niche}`\n"
            "_(សេចក្ដីព្រាងចាស់ដែលមិនត្រូវគ្នាត្រូវបានជម្រះ ប៉ុន្តែ Script ជោគជ័យត្រូវបានរក្សាទុកដដែល)_\n\n"
        )
        msg = notice_text + render_format_selection(chosen_niche)
        keyboard = get_format_selection_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
        return

    # ── MENU: CREATE SCRIPT ───────────────────
    elif action == "create":
        saved_niche = storage.get_user_niche(user_key)
        if not saved_niche:
            # First visit: choose niche
            navigation.go_to(user_key, Screens.NICHE_SELECTION)
            msg = render_niche_selection()
            keyboard = get_niche_selection_keyboard()
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
            return

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
            niche=saved_niche,
        )
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.FORMAT_SELECTION, draft_id=draft.id)

        msg = render_format_selection(saved_niche)
        keyboard = get_format_selection_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── MENU: COMEDY ──────────────────────────
    elif action == "comedy":
        saved_niche = storage.get_user_niche(user_key)
        if not saved_niche:
            navigation.go_to(user_key, Screens.NICHE_SELECTION)
            msg = render_niche_selection()
            keyboard = get_niche_selection_keyboard()
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
            return

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
            current_step="topic_or_ideas",
            owner=user_key,
            niche=saved_niche,
        )
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.TOPIC_OR_IDEAS, draft_id=draft.id)

        msg = render_topic_or_ideas(draft.format_id, draft.niche)
        keyboard = get_topic_or_ideas_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── TOPIC OR IDEAS CHOICES ────────────────
    elif action == "top_custom":
        draft_id = decoded.token
        draft = storage.get_draft(draft_id) if draft_id else None
        if not draft:
            await query.answer("⚠️ រកមិនឃើញទិន្នន័យព្រាងឡើយ។", show_alert=True)
            return
        if draft.owner and draft.owner != user_key:
            await query.answer("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Draft របស់អ្នកដទៃឡើយ!", show_alert=True)
            return
        draft.current_step = "topic"
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.TOPIC_INPUT, draft_id=draft.id)
        msg = render_topic_prompt(draft.format_id, draft.niche)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_back_home_keyboard())

    elif action == "top_ideas":
        draft_id = decoded.token
        draft = storage.get_draft(draft_id) if draft_id else None
        if not draft:
            await query.answer("⚠️ រកមិនឃើញទិន្នន័យព្រាងឡើយ។", show_alert=True)
            return
        if draft.owner and draft.owner != user_key:
            await query.answer("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Draft របស់អ្នកដទៃឡើយ!", show_alert=True)
            return
        from app.handlers.ideas import start_ideas_flow
        await start_ideas_flow(
            update,
            context,
            category=draft.niche,
            format_id=draft.format_id,
            draft_id=draft.id,
        )

    # ── MENU: IDEAS ───────────────────────────
    elif action == "ideas":
        saved_niche = storage.get_user_niche(user_key)
        from app.handlers.ideas import start_ideas_flow
        await start_ideas_flow(update, context, category=saved_niche or "ទូទៅ")

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

    # ── EDIT TOPIC IN DRAFT ───────────────────
    elif action == "edit_top":
        draft_id = decoded.token
        draft = storage.get_draft(draft_id) if draft_id else None
        if not draft:
            await query.answer("⚠️ រកមិនឃើញទិន្នន័យព្រាងឡើយ។", show_alert=True)
            return
        if draft.owner and draft.owner != user_key:
            await query.answer("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Draft របស់អ្នកដទៃឡើយ!", show_alert=True)
            return
        draft.current_step = "topic"
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.TOPIC_INPUT, draft_id=draft.id)
        msg = f"✏️ *កែប្រែប្រធានបទ*\n\nប្រធានបទបច្ចុប្បន្ន៖ *{draft.topic}*\n\n" + render_topic_prompt(draft.format_id, draft.niche)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_back_home_keyboard())

    # ── EDIT DURATION IN DRAFT ────────────────
    elif action == "edit_dur":
        draft_id = decoded.token
        draft = storage.get_draft(draft_id) if draft_id else None
        if not draft:
            await query.answer("⚠️ រកមិនឃើញទិន្នន័យព្រាងឡើយ។", show_alert=True)
            return
        if draft.owner and draft.owner != user_key:
            await query.answer("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Draft របស់អ្នកដទៃឡើយ!", show_alert=True)
            return
        navigation.go_to(user_key, Screens.DRAFT_DURATION, draft_id=draft.id)
        msg = "⏱️ *ជ្រើសរើសរយៈពេលវីដេអូសម្រាប់ Script នេះ (Duration)*\n\nសូមជ្រើសរើសរយៈពេលខាងក្រោម៖"
        keyboard = get_draft_duration_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    # ── EDIT FAILED REQUEST ───────────────────
    elif action == "edit_failed":
        req_id = decoded.token
        req = storage.get_generation_request(req_id) if req_id else None
        if not req:
            last_failed = storage.get_last_failed_request(user_key)
            if last_failed:
                req = last_failed[0]
        if not req:
            await query.answer("⚠️ រកមិនឃើញសំណើដែលបរាជ័យឡើយ។", show_alert=True)
            return
        if req.owner != user_key:
            await query.answer("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែសំណើរបស់អ្នកដទៃឡើយ!", show_alert=True)
            return
        from app.models import Draft
        draft = Draft.from_dict(req.draft_snapshot)
        draft.id = f"d_{uuid.uuid4().hex[:8]}"
        draft.revision = 1
        draft.current_step = "review"
        draft.owner = user_key
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.DRAFT_REVIEW, draft_id=draft.id)
        settings = storage.get_settings(user_key)
        msg = render_review(draft, settings["pace"])
        keyboard = get_review_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

async def render_current_screen(query, user_key: UserKey, screen: str, state, storage):
    """Renders the screen restored by Back action."""
    settings = storage.get_settings(user_key)

    if screen == Screens.HOME:
        msg = render_welcome(settings["duration"])
        keyboard = get_main_menu_keyboard()
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif screen == Screens.NICHE_SELECTION:
        msg = render_niche_selection()
        keyboard = get_niche_selection_keyboard()
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif screen == Screens.FORMAT_SELECTION:
        niche = storage.get_user_niche(user_key)
        draft = storage.get_draft(state.draft_id) if state.draft_id else None
        if not draft:
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
                niche=niche,
            )
            storage.save_draft(user_key, draft)
        msg = render_format_selection(niche)
        keyboard = get_format_selection_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif screen == Screens.TOPIC_OR_IDEAS:
        draft = storage.get_draft(state.draft_id) if state.draft_id else None
        if not draft:
            return await render_current_screen(query, user_key, Screens.FORMAT_SELECTION, state, storage)
        msg = render_topic_or_ideas(draft.format_id, draft.niche)
        keyboard = get_topic_or_ideas_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif screen == Screens.DRAFT_DURATION:
        draft = storage.get_draft(state.draft_id) if state.draft_id else None
        if not draft:
            return await render_current_screen(query, user_key, Screens.HOME, state, storage)
        msg = "⏱️ *ជ្រើសរើសរយៈពេលវីដេអូសម្រាប់ Script នេះ (Duration)*\n\nសូមជ្រើសរើសរយៈពេលខាងក្រោម៖"
        keyboard = get_draft_duration_keyboard(draft)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif screen == Screens.TOPIC_INPUT:
        draft = storage.get_draft(state.draft_id) if state.draft_id else None
        if not draft:
            return await render_current_screen(query, user_key, Screens.HOME, state, storage)
        msg = render_topic_prompt(draft.format_id, draft.niche)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_back_home_keyboard())

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
