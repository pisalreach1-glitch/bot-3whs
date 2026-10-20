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
    get_topic_or_ideas_keyboard,
    get_comedy_styles_keyboard,
)
from app.views import (
    render_topic_prompt,
    render_review,
    render_script_summary,
    render_failure,
    render_topic_or_ideas,
)
from app.services.generation import execute_generation_request
from app.handlers.commands import get_user_key
from app.telegram_io import safe_edit

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

    # Check ownership
    if draft.owner and draft.owner != user_key:
        await query.answer("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Draft របស់អ្នកដទៃឡើយ!", show_alert=True)
        return

    # Check stale revision
    if draft.revision != decoded.version_or_rev:
        await query.answer("⚠️ ប៊ូតុងនេះផុតសុពលភាពហើយ (Stale action)។", show_alert=True)
        return

    draft.format_id = decoded.action
    if not draft.niche:
        saved_niche = storage.get_user_niche(user_key)
        draft.niche = saved_niche or "ទូទៅ"

    if decoded.action == "comedy":
        draft.current_step = "comedy_style"
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.COMEDY_STYLE, draft_id=draft.id)
        msg = (
            "😂 *ជ្រើសរើសស្ទីលកំប្លែង (Comedy Style)*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 វិស័យ៖ `{draft.niche}`\n\n"
            "សូមជ្រើសរើសទម្រង់កំប្លែងដែលអ្នកចង់ផលិតខាងក្រោម៖"
        )
        await safe_edit(query, msg, reply_markup=get_comedy_styles_keyboard(draft))
        return

    draft.current_step = "topic_or_ideas"
    storage.save_draft(user_key, draft)
    navigation.go_to(user_key, Screens.TOPIC_OR_IDEAS, draft_id=draft.id)

    msg = render_topic_or_ideas(draft.format_id, draft.niche)
    await safe_edit(query, msg, reply_markup=get_topic_or_ideas_keyboard(draft))

async def handle_draft_duration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles d:<draft_token>:<revision>:<seconds>"""
    query = update.callback_query
    await query.answer()

    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    decoded = decode_callback(query.data)

    draft = storage.get_draft(decoded.token)
    if not draft:
        await query.answer("⚠️ រកមិនឃើញទិន្នន័យព្រាងឡើយ។", show_alert=True)
        return

    # Check ownership
    if draft.owner and draft.owner != user_key:
        await query.answer("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Draft របស់អ្នកដទៃឡើយ!", show_alert=True)
        return

    if draft.revision != decoded.version_or_rev:
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
    await safe_edit(query, msg, reply_markup=keyboard)

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

    # Check ownership
    if draft.owner and draft.owner != user_key:
        await query.answer("⚠️ អ្នកគ្មានសិទ្ធិបង្កើត Script ពី Draft របស់អ្នកដទៃឡើយ!", show_alert=True)
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
        evidence_snapshot = storage.get_recent_evidence_for_user(user_key, draft.evidence_ids)

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

    try:
        clean_topic = draft.topic.replace("_", "\\_").replace("*", "\\*")
        try:
            status_msg = await query.message.reply_text(
                f"⏳ *កំពុងបង្កើត Script វីដេអូ...*\n"
                f"_ប្រធានបទ: {clean_topic}_\n"
                f"_រយៈពេល: {draft.duration_seconds} វិនាទី_\n\n"
                "សូមរង់ចាំមួយភ្លែត...",
                parse_mode="Markdown",
                reply_markup=get_cancel_processing_keyboard(request_id),
            )
        except Exception:
            status_msg = await query.message.reply_text(
                f"⏳ កំពុងបង្កើត Script វីដេអូ...\n"
                f"ប្រធានបទ: {draft.topic}\n"
                f"រយៈពេល: {draft.duration_seconds} វិនាទី\n\n"
                "សូមរង់ចាំមួយភ្លែត...",
                reply_markup=get_cancel_processing_keyboard(request_id),
            )

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
            await safe_edit(status_msg, summary_msg, reply_markup=actions_kb)
        else:
            fail_msg = render_failure(result.error_code or "ERROR", result.user_message_km)
            fail_kb = get_failure_keyboard(result.request_id or request_id)
            await safe_edit(status_msg, fail_msg, reply_markup=fail_kb)

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

    try:
        raw_topic = request.draft_snapshot.get('topic', '')
        clean_topic = raw_topic.replace("_", "\\_").replace("*", "\\*")
        try:
            status_msg = await query.message.reply_text(
                f"🔄 *កំពុងសាកល្បងសំណើឡើងវិញ...*\n"
                f"_ប្រធានបទ: {clean_topic}_\n\n"
                "សូមរង់ចាំមួយភ្លែត...",
                parse_mode="Markdown",
                reply_markup=get_cancel_processing_keyboard(request.id),
            )
        except Exception:
            status_msg = await query.message.reply_text(
                f"🔄 កំពុងសាកល្បងសំណើឡើងវិញ...\n"
                f"ប្រធានបទ: {raw_topic}\n\n"
                "សូមរង់ចាំមួយភ្លែត...",
                reply_markup=get_cancel_processing_keyboard(request.id),
            )

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
            await safe_edit(status_msg, summary_msg, reply_markup=actions_kb)
        else:
            fail_msg = render_failure(result.error_code or "ERROR", result.user_message_km)
            fail_kb = get_failure_keyboard(request.id)
            await safe_edit(status_msg, fail_msg, reply_markup=fail_kb)
    finally:
        await task_mgr.finish_request(user_key, token)
