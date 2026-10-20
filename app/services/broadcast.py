"""
app/services/broadcast.py - Daily Ideas Broadcast Service.

Generates general daily ideas ONCE outside the subscriber loop and delivers
to all active subscribers with message splitting and Markdown safety.
"""

import logging
from app.models import UserKey
from app.storage import Storage
from ai_service import AIService
from app.services.ideas import get_or_generate_ideas
from app.views import render_ideas_batch
from app.telegram_io import split_message

logger = logging.getLogger(__name__)

async def send_daily_broadcast(bot_client, storage: Storage, ai: AIService):
    """Broadcasts daily content ideas to all active subscribers."""
    logger.info("Starting daily subscriber broadcast...")
    subscribers = storage.get_active_subscribers()
    sub_chat_ids = [sub.chat_id for sub in subscribers]

    try:
        import bot
        if hasattr(bot, "subscribers") and bot.subscribers:
            for s in bot.subscribers:
                if s not in sub_chat_ids:
                    sub_chat_ids.append(s)
    except Exception:
        pass

    if not sub_chat_ids:
        logger.info("No active subscribers for broadcast.")
        return

    # Generate general daily ideas ONCE outside the subscriber loop
    if hasattr(ai, "generate_daily_ideas"):
        import asyncio
        res = ai.generate_daily_ideas("ទូទៅ")
        ideas_text = await res if asyncio.iscoroutine(res) else res
    else:
        system_key = UserKey(chat_id=0, user_id=0)
        batch_token, ideas, evidence, failure_msg = await get_or_generate_ideas(
            user_key=system_key,
            category="ទូទៅ",
            storage=storage,
            ai=ai,
        )
        if failure_msg or not ideas:
            logger.warning(f"Daily broadcast idea generation failed: {failure_msg}. Aborting delivery.")
            return
        ideas_text = render_ideas_batch(ideas, evidence, "ទូទៅ")

    full_message = (
        "☀️ *អរុណសួស្តី! គំនិតមាតិកាវីដេអូប្រចាំថ្ងៃ* 💡\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{ideas_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 _ចុច /start ដើម្បីជ្រើសរើសទម្រង់មាតិកា រួចបង្កើត Script ពេញលេញភ្លាមៗ!_"
    )

    chunks = split_message(full_message, max_length=4000)
    # Deduplicate delivery per chat_id
    delivered_chats = set()

    for chat_id in sub_chat_ids:
        if chat_id in delivered_chats:
            continue
        delivered_chats.add(chat_id)

        for chunk in chunks:
            try:
                await bot_client.send_message(chat_id=chat_id, text=chunk, parse_mode="Markdown")
            except Exception:
                try:
                    await bot_client.send_message(chat_id=chat_id, text=chunk)
                except Exception as e:
                    logger.error(f"Failed to deliver daily broadcast to chat {chat_id}: {e}")

    logger.info(f"Daily broadcast delivered to {len(delivered_chats)} subscribers.")
