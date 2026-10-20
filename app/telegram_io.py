"""
app/telegram_io.py - Message splitting and safe formatting for Telegram.

Splits long messages (>4000 characters) cleanly on newlines and handles
Markdown formatting failures gracefully with plain-text fallback.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

def split_message(text: str, max_length: int = 4000) -> List[str]:
    """Splits a long message into safe Telegram chunks (<= 4000 chars), breaking at newlines when possible."""
    if len(text) <= max_length:
        return [text]
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
        # Find clean break point
        idx = remaining.rfind("\n", 0, max_length)
        if idx == -1 or idx < max_length // 2:
            idx = remaining.rfind(" ", 0, max_length)
        if idx == -1:
            idx = max_length

        chunks.append(remaining[:idx].rstrip())
        remaining = remaining[idx:].lstrip()
    return chunks

async def safe_reply(target, text: str, reply_markup=None):
    """Sends message with Markdown parse mode, falling back to plain text if syntax fails."""
    chunks = split_message(text)
    msg_target = target.message if hasattr(target, "message") and target.message else target
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await msg_target.reply_text(chunk, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            try:
                await msg_target.reply_text(chunk, reply_markup=markup)
            except Exception as e:
                logger.error(f"Failed to safe_reply: {e}")

async def safe_edit(target, text: str, reply_markup=None):
    """Edits status message or callback query with first chunk, and replies with any subsequent chunks."""
    chunks = split_message(text)
    first_markup = reply_markup if len(chunks) == 1 else None

    edit_fn = None
    reply_target = None

    if hasattr(target, "edit_text"):
        # Message
        edit_fn = target.edit_text
        reply_target = target
    elif hasattr(target, "edit_message_text"):
        # CallbackQuery
        edit_fn = target.edit_message_text
        reply_target = getattr(target, "message", None)
    else:
        reply_target = target

    if edit_fn:
        try:
            await edit_fn(chunks[0], parse_mode="Markdown", reply_markup=first_markup)
        except Exception:
            try:
                await edit_fn(chunks[0], reply_markup=first_markup)
            except Exception as e:
                logger.error(f"Failed to edit message: {e}")
                if reply_target and hasattr(reply_target, "reply_text"):
                    await safe_reply(reply_target, chunks[0], reply_markup=first_markup)
    elif reply_target:
        await safe_reply(reply_target, chunks[0], reply_markup=first_markup)

    if reply_target and hasattr(reply_target, "reply_text"):
        for i, chunk in enumerate(chunks[1:], start=1):
            markup = reply_markup if i == len(chunks) - 1 else None
            try:
                await reply_target.reply_text(chunk, parse_mode="Markdown", reply_markup=markup)
            except Exception:
                try:
                    await reply_target.reply_text(chunk, reply_markup=markup)
                except Exception as e:
                    logger.error(f"Failed to reply subsequent chunk: {e}")
