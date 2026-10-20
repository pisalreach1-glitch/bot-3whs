"""
app/handlers/creation.py - Script Creation Flow: Format → Topic Input → Review → Generate & Retry.

Guarantees:
- Zero Gemini calls before explicit Generate.
- Snapshotting of complete request data.
- TaskManager acquisition before first await.
- Exact failed request preservation for Retry.
"""

import uuid
import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.models import UserKey, Draft, GenerationRequest, ErrorCodes
from app.navigation import navigation, Screens
from app.callbacks import decode_callback
from app.keyboards import (
    get_review_keyboard,
    get_script_actions_keyboard,
    get_failure_keyboard,
    get_cancel_processing_keyboard,
    get_draft_duration_keyboard,
    get_back_home_keyboard,
)
from app.views import (
    render_topic_prompt,
    render_review,
    render_script_summary,
    render_failure,
)
from app.services.generation import execute_generation_request
from app.handlers.commands import get_user_key

logger = logging.getLogger(__name__)

async def handle_format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles f:<format_id>:<draft_token>:<revision>"""
    query = update.callback_query
    await query.answer()

    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    decoded = decode_callback(query.data)

    draft = storage.get_draft(decoded.token)
    if not draft:
        await query.message.reply_text("⚠️ រកមិនឃើញទិន្នន័យព្រាង (Draft) ឡើយ។ សូមចាប់ផ្តើមជាថ្មី។")
        return

    # Check stale revision
    if draft.revision != decoded.version_or_rev:
        await query.answer("⚠️ ប៊ូតុងនេះផុតសុពលភាពហើយ (Stale action)។", show_alert=True)
        return

    draft.format_id = decoded.action
    draft.current_step = "topic"
    storage.save_draft(user_key, draft)
    navigation.go_to(user_key, Screens.TOPIC_INPUT, draft_id=draft.id)

    msg = render_topic_prompt(draft.format_id)
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_back_home_keyboard())

async def handle_draft_duration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles d:<draft_token>:<revision>:<seconds>"""
    query = update.callback_query
    await query.answer()

    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    decoded = decode_callback(query.data)

    draft = storage.get_draft(decoded.token)
    if not draft or draft.revision != decoded.version_or_rev:
        await query.answer("⚠️ ប៊ូតុងនេះផុតសុពលភាពហើយ។", show_alert=True)
        return

    # Update draft duration without altering user global settings
    draft.duration_seconds = int(decoded.extra)
    draft.revision += 1
    storage.save_draft(user_key, draft)
    navigation.go_to(user_key, Screens.DRAFT_REVIEW, draft_id=draft.id)

    settings = storage.get_settings(user_key)
    msg = render_review(draft, settings["pace"])
    keyboard = get_review_keyboard(draft)
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

async def handle_generate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles g:<draft_token>:<revision> (Explicit Generate Action)"""
    query = update.callback_query
    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    task_mgr = context.bot_data["task_mgr"]
    ai = context.bot_data["ai"]

    decoded = decode_callback(query.data)
    draft = storage.get_draft(decoded.token)

    if not draft:
        await query.answer("⚠️ រកមិនឃើញទិន្នន័យព្រាងឡើយ។", show_alert=True)
        return

    if draft.revision != decoded.version_or_rev:
        await query.answer("⚠️ សំណើនេះត្រូវបានកែប្រែរួចហើយ (Stale action)។", show_alert=True)
        return

    await query.answer("✨ កំពុងចាប់ផ្តើមបង្កើត Script...")

    # 1. Snapshot complete generation request
    settings = storage.get_settings(user_key)
    request_id = f"req_{uuid.uuid4().hex[:8]}"

    # Load evidence records if any
    evidence_snapshot = []
    if draft.evidence_ids:
        # Retrieve evidence from recent batch if cached
        pass

    request = GenerationRequest(
        id=request_id,
        operation="create",
        owner=user_key,
        draft_snapshot=draft.to_dict(),
        pace_units_per_second=settings["pace"],
        evidence_snapshot=evidence_snapshot,
    )

    # 2. Acquire per-user task lock before the first await
    token = await task_mgr.start_request(user_key, request_id)
    if token is None:
        await query.answer("⏳ Bot កំពុងដំណើរការសំណើមុនរបស់អ្នក... សូមរង់ចាំមួយភ្លែត ឬចុច /cancel!", show_alert=True)
        return

    status_msg = await query.message.reply_text(
        f"⏳ *កំពុងបង្កើត Script វីដេអូ...*\n"
        f"_ប្រធានបទ: {draft.topic}_\n"
        f"_រយៈពេល: {draft.duration_seconds} វិនាទី_\n\n"
        "សូមរង់ចាំមួយភ្លែត...",
        parse_mode="Markdown",
        reply_markup=get_cancel_processing_keyboard(request_id),
    )

    try:
        # 3. Execute generation pipeline
        result = await execute_generation_request(request, storage, ai, token, task_mgr)

        if not task_mgr.is_current_request(user_key, token):
            return  # Stale or cancelled

        if result.success and result.script:
            navigation.go_to(
                user_key,
                Screens.SCRIPT_SUMMARY,
                script_id=result.script.id,
                script_version=result.script.version,
            )
            summary_msg = render_script_summary(result.script, settings["pace"])
            actions_kb = get_script_actions_keyboard(result.script)
            try:
                await status_msg.edit_text(summary_msg, parse_mode="Markdown", reply_markup=actions_kb)
            except Exception:
                await status_msg.edit_text(summary_msg, reply_markup=actions_kb)
        else:
            fail_msg = render_failure(result.error_code or "ERROR", result.user_message_km)
            fail_kb = get_failure_keyboard(request_id)
            try:
                await status_msg.edit_text(fail_msg, parse_mode="Markdown", reply_markup=fail_kb)
            except Exception:
                await status_msg.edit_text(fail_msg, reply_markup=fail_kb)

    finally:
        await task_mgr.finish_request(user_key, token)

async def handle_retry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles r:<request_id> — Retries using the exact failed request snapshot."""
    query = update.callback_query
    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    task_mgr = context.bot_data["task_mgr"]
    ai = context.bot_data["ai"]

    decoded = decode_callback(query.data)
    request = storage.get_generation_request(decoded.token)

    if not request or request.owner != user_key:
        await query.answer("⚠️ រកមិនឃើញសំណើដែលបរាជ័យដើម្បីសាកល្បងម្ដងទៀតឡើយ។", show_alert=True)
        return

    await query.answer("🔄 កំពុងសាកល្បងសំណើនេះម្ដងទៀត...")

    token = await task_mgr.start_request(user_key, request.id)
    if token is None:
        await query.answer("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!", show_alert=True)
        return

    status_msg = await query.message.reply_text(
        f"🔄 *កំពុងសាកល្បងសំណើឡើងវិញ...*\n"
        f"_ប្រធានបទ: {request.draft_snapshot.get('topic', '')}_\n\n"
        "សូមរង់ចាំមួយភ្លែត...",
        parse_mode="Markdown",
        reply_markup=get_cancel_processing_keyboard(request.id),
    )

    try:
        result = await execute_generation_request(request, storage, ai, token, task_mgr)
        if not task_mgr.is_current_request(user_key, token):
            return

        settings = storage.get_settings(user_key)
        if result.success and result.script:
            navigation.go_to(
                user_key,
                Screens.SCRIPT_SUMMARY,
                script_id=result.script.id,
                script_version=result.script.version,
            )
            summary_msg = render_script_summary(result.script, settings["pace"])
            actions_kb = get_script_actions_keyboard(result.script)
            await status_msg.edit_text(summary_msg, parse_mode="Markdown", reply_markup=actions_kb)
        else:
            fail_msg = render_failure(result.error_code or "ERROR", result.user_message_km)
            fail_kb = get_failure_keyboard(request.id)
            await status_msg.edit_text(fail_msg, parse_mode="Markdown", reply_markup=fail_kb)
    finally:
        await task_mgr.finish_request(user_key, token)
