"""
app/handlers/scripts.py - Saved Script Views (Summary, Read, Shots, Caption) and Refinements Routing.

Guarantees:
- Switching views makes ZERO Gemini calls.
- Shorten, Regenerate, and Hook applications create new validated versions atomically.
- Stale or invalid buttons fail safely without altering other scripts.
"""

import uuid
import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.models import UserKey
from app.navigation import navigation, Screens
from app.callbacks import decode_callback
from app.keyboards import (
    get_script_actions_keyboard,
    get_hook_options_keyboard,
    get_failure_keyboard,
    get_cancel_processing_keyboard,
    get_review_keyboard,
)
from app.views import (
    render_script_summary,
    render_script_read,
    render_script_shots,
    render_script_caption,
    render_hook_options,
    render_failure,
    render_review,
)
from app.services.refinements import (
    shorten_script,
    regenerate_script,
    generate_hook_options,
    apply_hook_option,
)
from app.handlers.commands import get_user_key
from app.telegram_io import safe_edit

logger = logging.getLogger(__name__)

async def handle_script_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles s:<script_id>:<version>:<action> callbacks."""
    query = update.callback_query
    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    task_mgr = context.bot_data["task_mgr"]
    ai = context.bot_data["ai"]

    decoded = decode_callback(query.data)
    script_id = decoded.token
    version = decoded.version_or_rev
    action = decoded.action

    script = storage.get_script(script_id, version)
    if not script:
        await query.answer("⚠️ រកមិនឃើញ Script នេះឡើយ។", show_alert=True)
        return

    # Check ownership
    if script.owner != user_key:
        await query.answer("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Script របស់អ្នកដទៃឡើយ។", show_alert=True)
        return

    settings = storage.get_settings(user_key)
    pace = script.request_snapshot.pace_units_per_second or settings["pace"]

    # ── ZERO AI CALL VIEWS ────────────────────
    if action == "read":
        await query.answer("📖 ប្លង់ពាក្យនិយាយ")
        navigation.go_to(user_key, Screens.SCRIPT_READ, script_id=script_id, script_version=version)
        msg = render_script_read(script)
        await safe_edit(query, msg, reply_markup=get_script_actions_keyboard(script))

    elif action == "shots":
        await query.answer("🎥 ប្លង់ថតលម្អិត")
        navigation.go_to(user_key, Screens.SCRIPT_SHOTS, script_id=script_id, script_version=version)
        msg = render_script_shots(script, pace)
        await safe_edit(query, msg, reply_markup=get_script_actions_keyboard(script))

    elif action == "caption":
        await query.answer("📝 Caption & CTA")
        navigation.go_to(user_key, Screens.SCRIPT_CAPTION, script_id=script_id, script_version=version)
        msg = render_script_caption(script)
        await safe_edit(query, msg, reply_markup=get_script_actions_keyboard(script))

    elif action == "edit_req":
        await query.answer("✏️ កែប្រែសំណើ")
        from app.models import Draft
        # Re-create a draft from script snapshot
        draft_dict = script.request_snapshot.draft_snapshot
        draft = Draft.from_dict(draft_dict)
        draft.id = f"d_{uuid.uuid4().hex[:8]}"
        draft.revision += 1
        draft.owner = user_key
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.DRAFT_REVIEW, draft_id=draft.id)
        msg = render_review(draft, pace)
        await safe_edit(query, msg, reply_markup=get_review_keyboard(draft))

    # ── REFINEMENT ACTIONS (AI CALLS) ─────────
    elif action == "shorten":
        token = await task_mgr.start_request(user_key, f"short_{uuid.uuid4().hex[:6]}")
        if token is None:
            await query.answer("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!", show_alert=True)
            return
        await query.answer("✂️ កំពុងសង្ខេបឱ្យខ្លី...")
        status_msg = await query.message.reply_text(
            "✂️ *កំពុងសង្ខេប Script ឱ្យកាន់តែខ្លី ខ្លឹម និង Fast-paced...*\nសូមរង់ចាំមួយភ្លែត...",
            parse_mode="Markdown",
            reply_markup=get_cancel_processing_keyboard(f"short_{script_id}"),
        )
        try:
            res = await shorten_script(user_key, script_id, version, storage, ai, task_mgr, token)
            if not task_mgr.is_current_request(user_key, token):
                return
            if res.success and res.script:
                navigation.go_to(user_key, Screens.SCRIPT_SUMMARY, script_id=res.script.id, script_version=res.script.version)
                summary_msg = render_script_summary(res.script, pace)
                await safe_edit(status_msg, summary_msg, reply_markup=get_script_actions_keyboard(res.script))
            else:
                fail_req_id = res.request_id or script_id
                fail_msg = render_failure(res.error_code or "ERROR", res.user_message_km)
                await safe_edit(status_msg, fail_msg, reply_markup=get_failure_keyboard(fail_req_id))
        finally:
            await task_mgr.finish_request(user_key, token)

    elif action == "regen":
        token = await task_mgr.start_request(user_key, f"regen_{uuid.uuid4().hex[:6]}")
        if token is None:
            await query.answer("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!", show_alert=True)
            return
        await query.answer("🔁 កំពុងបង្កើតកំណែថ្មី...")
        status_msg = await query.message.reply_text(
            "🔁 *កំពុងបង្កើត Script ឡើងវិញ (កំណែថ្មី)...*\nសូមរង់ចាំមួយភ្លែត...",
            parse_mode="Markdown",
            reply_markup=get_cancel_processing_keyboard(f"regen_{script_id}"),
        )
        try:
            res = await regenerate_script(user_key, script_id, version, storage, ai, task_mgr, token)
            if not task_mgr.is_current_request(user_key, token):
                return
            if res.success and res.script:
                navigation.go_to(user_key, Screens.SCRIPT_SUMMARY, script_id=res.script.id, script_version=res.script.version)
                summary_msg = render_script_summary(res.script, pace)
                await safe_edit(status_msg, summary_msg, reply_markup=get_script_actions_keyboard(res.script))
            else:
                fail_req_id = res.request_id or script_id
                fail_msg = render_failure(res.error_code or "ERROR", res.user_message_km)
                await safe_edit(status_msg, fail_msg, reply_markup=get_failure_keyboard(fail_req_id))
        finally:
            await task_mgr.finish_request(user_key, token)

    elif action == "hooks":
        token = await task_mgr.start_request(user_key, f"hooks_{uuid.uuid4().hex[:6]}")
        if token is None:
            await query.answer("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!", show_alert=True)
            return
        await query.answer("🎣 កំពុងបង្កើតជម្រើស Hook ថ្មី...")
        status_msg = await query.message.reply_text(
            "🎣 *កំពុងរៀបចំជម្រើស Hook ថ្មីទាំង ៣ បែប...*\nសូមរង់ចាំមួយភ្លែត...",
            parse_mode="Markdown",
            reply_markup=get_cancel_processing_keyboard(f"hooks_{script_id}"),
        )
        try:
            opt_token, hooks, err = await generate_hook_options(user_key, script_id, version, storage, ai)
            if not task_mgr.is_current_request(user_key, token):
                return
            if err or not hooks:
                await safe_edit(status_msg, err or "⚠️ មិនអាចបង្កើត Hook ថ្មីបានឡើយ។", reply_markup=get_script_actions_keyboard(script))
                return
            navigation.go_to(user_key, Screens.HOOK_OPTIONS, script_id=script_id, script_version=version)
            msg = render_hook_options(script, hooks)
            kb = get_hook_options_keyboard(opt_token, len(hooks))
            await safe_edit(status_msg, msg, reply_markup=kb)
        finally:
            await task_mgr.finish_request(user_key, token)

async def handle_hook_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles h:<options_token>:<option_index> — Applies selected hook to Scene 1."""
    query = update.callback_query
    await query.answer()

    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    decoded = decode_callback(query.data)

    options_token = decoded.token
    opt_idx = int(decoded.extra)

    opts_data = storage.get_hook_options(options_token)
    if not opts_data:
        await query.answer("⚠️ ជម្រើស Hook នេះផុតសុពលភាពហើយ។", show_alert=True)
        return

    script_id = opts_data["script_id"]
    version = opts_data["script_version"]

    res = apply_hook_option(user_key, script_id, version, opt_idx, options_token, storage)
    if res.success and res.script:
        settings = storage.get_settings(user_key)
        navigation.go_to(user_key, Screens.SCRIPT_SUMMARY, script_id=res.script.id, script_version=res.script.version)
        msg = f"✅ *បានអនុវត្តជម្រើស Hook ទី {opt_idx} ជោគជ័យ!* (បង្កើតជាកំណែទី {res.script.version})\n\n" + render_script_summary(res.script, settings["pace"])
        await safe_edit(query, msg, reply_markup=get_script_actions_keyboard(res.script))
    else:
        await safe_reply(query.message, res.user_message_km)
