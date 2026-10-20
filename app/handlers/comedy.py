"""
app/handlers/comedy.py - Short Comedy Video Flow: Style Selection → Actors Count → Topic Input → Review.

Defaults:
- Everyday relatable Khmer comedy
- 1 actor playing up to 2 characters
- 60 seconds
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.models import UserKey
from app.navigation import navigation, Screens
from app.callbacks import decode_callback
from app.keyboards import get_comedy_actors_keyboard, get_back_home_keyboard
from app.handlers.commands import get_user_key
from app.telegram_io import safe_edit

logger = logging.getLogger(__name__)

async def handle_comedy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles c:sty:... and c:act:... callbacks."""
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

    # 1. Select Style -> go to Actors
    if decoded.action == "sty":
        draft.comedy_style = decoded.extra
        draft.revision += 1
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.COMEDY_ACTORS, draft_id=draft.id)

        msg = (
            "👥 *ចំនួនតួអង្គសម្ដែង (Actor Count)*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"• ស្ទីលជ្រើសរើស៖ *{draft.comedy_style}*\n\n"
            "សូមជ្រើសរើសចំនួនតួអង្គដែលអ្នកចង់ឱ្យសម្ដែងក្នុងវីដេអូ៖"
        )
        keyboard = get_comedy_actors_keyboard(draft)
        await safe_edit(query, msg, reply_markup=keyboard)

    # 2. Select Actors -> go to Topic Input
    elif decoded.action == "act":
        draft.actor_count = int(decoded.extra)
        draft.revision += 1
        draft.current_step = "topic"
        storage.save_draft(user_key, draft)
        navigation.go_to(user_key, Screens.TOPIC_INPUT, draft_id=draft.id)

        msg = (
            "🎭 *សូមបញ្ចូលប្រធានបទ ឬស្ថានភាពកំប្លែង*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"• ស្ទីល៖ *{draft.comedy_style}* | តួអង្គ៖ *{draft.actor_count} នាក់*\n\n"
            "សូមវាយប្រធានបទ ស្ថានភាព ឬគំនិតកំប្លែងដែលអ្នកចង់ផលិត៖\n\n"
            "_ឧទាហរណ៍៖_\n"
            "• «ពេលម៉ែប្រើទៅទិញម្ទេស តែភ្លេចទិញប្រហុក»\n"
            "• «ពេលមិត្តភក្តិខ្ចីលុយ ដល់ពេលសងបែរជាខឹងយើងវិញ»\n"
            "• «ថ្ងៃដំបូងចូលធ្វើការ ធ្វើចេះគ្រប់រឿង»\n"
            "• «ពេលសុំច្បាប់មេ តែចៃដន្យជួបមេនៅផ្សារ»"
        )
        await safe_edit(query, msg, reply_markup=get_back_home_keyboard())
