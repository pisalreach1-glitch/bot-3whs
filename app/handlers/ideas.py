"""
app/handlers/ideas.py - Daily Ideas Flow and Idea-to-Draft Selection.
"""

import uuid
import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.models import UserKey, Draft
from app.navigation import navigation, Screens
from app.callbacks import decode_callback
from app.keyboards import get_ideas_keyboard, get_review_keyboard, get_back_home_keyboard
from app.views import render_ideas_batch, render_review
from app.services.ideas import get_or_generate_ideas
from app.handlers.commands import get_user_key
from script_models import parse_duration_seconds

logger = logging.getLogger(__name__)

async def start_ideas_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str = "ទូទៅ"):
    """Fetches or generates daily content ideas and presents numbered selection buttons."""
    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    ai = context.bot_data["ai"]
    task_mgr = context.bot_data["task_mgr"]

    target = update.message or (update.callback_query.message if update.callback_query else None)
    status_msg = await target.reply_text("💡 *កំពុងស្វែងរកព័ត៌មានថ្មីៗ និងរៀបចំគំនិតមាតិកា...*", parse_mode="Markdown")

    token = await task_mgr.start_request(user_key, f"ideas_{uuid.uuid4().hex[:6]}")
    if token is None:
        await target.reply_text("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!")
        return

    try:
        batch_token, ideas, evidence, failure_msg = await get_or_generate_ideas(
            user_key=user_key,
            category=category,
            storage=storage,
            ai=ai,
        )

        if not task_mgr.is_current_request(user_key, token):
            return

        if failure_msg or not ideas:
            # Sourced generation rejected due to citation failure or error
            err_text = failure_msg or "⚠️ មិនអាចបង្កើតគំនិតមាតិកាបានឡើយ។"
            await status_msg.edit_text(err_text, parse_mode="Markdown", reply_markup=get_back_home_keyboard())
            return

        navigation.go_to(user_key, Screens.IDEA_RESULTS)
        ideas_text = render_ideas_batch(ideas, evidence, category)
        keyboard = get_ideas_keyboard(batch_token, len(ideas))
        await status_msg.edit_text(ideas_text, parse_mode="Markdown", reply_markup=keyboard)

    finally:
        await task_mgr.finish_request(user_key, token)

async def handle_idea_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles i:<batch_token>:<idea_index>
    Selecting an idea creates a draft, preserves evidence IDs, and opens Draft Review.
    """
    query = update.callback_query
    await query.answer()

    user_key = get_user_key(update)
    storage = context.bot_data["storage"]
    decoded = decode_callback(query.data)

    batch_token = decoded.token
    idea_idx = int(decoded.extra)

    batch = storage.get_idea_batch(batch_token)
    if not batch:
        await query.answer("⚠️ បញ្ជីគំនិតនេះផុតកំណត់ហើយ។ សូមទាញយកគំនិតថ្មី។", show_alert=True)
        return

    if idea_idx < 1 or idea_idx > len(batch["ideas"]):
        await query.answer("⚠️ លេខគំនិតមិនត្រឹមត្រូវ។", show_alert=True)
        return

    chosen_idea = batch["ideas"][idea_idx - 1]
    settings = storage.get_settings(user_key)
    dur_s = parse_duration_seconds(settings["duration"])

    # Create new draft initialized with the selected idea
    draft = Draft(
        id=f"d_{uuid.uuid4().hex[:8]}",
        revision=1,
        format_id=chosen_idea.suggested_format or "3whs",
        topic=chosen_idea.topic,
        duration_seconds=dur_s,
        audience=chosen_idea.topic,
        evidence_ids=[str(s) for s in chosen_idea.source_ids],
        current_step="review",
    )
    storage.save_draft(user_key, draft)
    navigation.go_to(user_key, Screens.DRAFT_REVIEW, draft_id=draft.id)

    msg = (
        f"🎯 *អ្នកបានជ្រើសរើសគំនិតទី {chosen_idea.id}៖*\n"
        f"_«{chosen_idea.topic}»_\n\n"
        + render_review(draft, settings["pace"])
    )
    keyboard = get_review_keyboard(draft)
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)
