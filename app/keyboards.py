"""
app/keyboards.py - All Telegram Inline Keyboards using compact callback data.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.callbacks import (
    encode_menu,
    encode_format,
    encode_duration,
    encode_generate,
    encode_idea_pick,
    encode_script_action,
    encode_hook_pick,
    encode_retry,
    encode_cancel,
    encode_nav,
    encode_setting,
    encode_comedy_style,
    encode_comedy_actors,
)
from app.models import Draft, SavedScript, GenerationRequest

FORMAT_DEFINITIONS = [
    ("3whs", "🎬 3WHs Hook Script"),
    ("pov", "🎭 POV / Storytelling"),
    ("myth", "⚡️ Myth vs Reality"),
    ("transform", "🔄 Before & After"),
    ("hottake", "🌶 Hot Take / Opinion"),
    ("toplist", "📋 Top List / Ranking"),
    ("comedy", "😂 Comedy"),
]

NICHE_DEFINITIONS = [
    ("food", "🍜 Food / Cooking"),
    ("coffee", "☕️ Coffee / Beverages"),
    ("sales", "🛍 Sales / Online Business"),
    ("education", "📚 Education / Skills"),
    ("tech", "📱 Technology / AI"),
    ("selfdev", "🌱 Personal Development"),
    ("custom", "✏️ Custom niche"),
]

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Main menu:
    🎬 បង្កើត Script
    😂 បង្កើតកំប្លែង
    💡 រកគំនិតមាតិកា
    📂 Script ចុងក្រោយ
    ⚙️ ការកំណត់
    ❓ របៀបប្រើ
    """
    keyboard = [
        [
            InlineKeyboardButton("🎬 បង្កើត Script", callback_data=encode_menu("create")),
            InlineKeyboardButton("😂 បង្កើតកំប្លែង", callback_data=encode_menu("comedy")),
        ],
        [
            InlineKeyboardButton("💡 រកគំនិតមាតិកា", callback_data=encode_menu("ideas")),
            InlineKeyboardButton("📂 Script ចុងក្រោយ", callback_data=encode_menu("last")),
        ],
        [
            InlineKeyboardButton("⚙️ ការកំណត់", callback_data=encode_menu("settings")),
            InlineKeyboardButton("❓ របៀបប្រើ", callback_data=encode_menu("help")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_niche_selection_keyboard() -> InlineKeyboardMarkup:
    """Niche selection keyboard showing preset niches, custom niche, and Home."""
    keyboard = []
    for niche_id, label in NICHE_DEFINITIONS:
        keyboard.append([
            InlineKeyboardButton(label, callback_data=encode_menu(f"niche:{niche_id}"))
        ])
    keyboard.append([
        InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
    ])
    return InlineKeyboardMarkup(keyboard)

def get_format_selection_keyboard(draft: Draft) -> InlineKeyboardMarkup:
    """Format submenu showing Change Niche, all 7 content formats, Back and Home."""
    keyboard = [
        [InlineKeyboardButton("✏️ ប្ដូរវិស័យ", callback_data=encode_menu("change_niche"))]
    ]
    for fmt_id, label in FORMAT_DEFINITIONS:
        keyboard.append([
            InlineKeyboardButton(label, callback_data=encode_format(fmt_id, draft.id, draft.revision))
        ])
    keyboard.append([
        InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data=encode_nav("back")),
        InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
    ])
    return InlineKeyboardMarkup(keyboard)

def get_topic_or_ideas_keyboard(draft: Draft) -> InlineKeyboardMarkup:
    """Offers choice between typing custom topic or requesting AI ideas for chosen niche and format."""
    keyboard = [
        [InlineKeyboardButton("✏️ ខ្ញុំមានប្រធានបទ", callback_data=encode_menu(f"top_custom:{draft.id}"))],
        [InlineKeyboardButton("💡 ស្នើគំនិតក្នុងវិស័យនេះ", callback_data=encode_menu(f"top_ideas:{draft.id}"))],
        [
            InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data=encode_nav("back")),
            InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_review_keyboard(draft: Draft) -> InlineKeyboardMarkup:
    """
    Review keyboard:
    ✨ បង្កើត Script
    ✏️ កែប្រធានបទ
    ⏱️ ប្ដូររយៈពេល
    ⬅️ ត្រឡប់ក្រោយ
    🏠 Menu
    """
    keyboard = [
        [InlineKeyboardButton("✨ បង្កើត Script", callback_data=encode_generate(draft.id, draft.revision))],
        [
            InlineKeyboardButton("✏️ កែប្រធានបទ", callback_data=encode_menu(f"edit_top:{draft.id}")),
            InlineKeyboardButton("⏱️ ប្ដូររយៈពេល", callback_data=encode_menu(f"edit_dur:{draft.id}")),
        ],
        [
            InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data=encode_nav("back")),
            InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_draft_duration_keyboard(draft: Draft) -> InlineKeyboardMarkup:
    """Draft-specific duration selection without mutating user default settings."""
    def mark(s):
        return f"✅ {s}s" if draft.duration_seconds == s else f"{s}s"

    keyboard = [
        [
            InlineKeyboardButton(mark(60), callback_data=encode_duration(draft.id, draft.revision, 60)),
            InlineKeyboardButton(mark(120), callback_data=encode_duration(draft.id, draft.revision, 120)),
        ],
        [
            InlineKeyboardButton(mark(180), callback_data=encode_duration(draft.id, draft.revision, 180)),
            InlineKeyboardButton(mark(300), callback_data=encode_duration(draft.id, draft.revision, 300)),
        ],
        [
            InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data=encode_nav("back")),
            InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_script_actions_keyboard(script: SavedScript) -> InlineKeyboardMarkup:
    """
    Script actions keyboard:
    📖 ពាក្យនិយាយ
    🎥 ប្លង់ថត
    📝 Caption
    🎣 ប្ដូរ Hook
    ✂️ កាត់ពាក្យឲ្យខ្លី
    🔁 បង្កើតកំណែថ្មី
    ✏️ កែសំណើ
    🏠 Menu
    """
    sid = script.id
    ver = script.version
    keyboard = [
        [
            InlineKeyboardButton("📖 ពាក្យនិយាយ", callback_data=encode_script_action(sid, ver, "read")),
            InlineKeyboardButton("🎥 ប្លង់ថត", callback_data=encode_script_action(sid, ver, "shots")),
            InlineKeyboardButton("📝 Caption", callback_data=encode_script_action(sid, ver, "caption")),
        ],
        [
            InlineKeyboardButton("🎣 ប្ដូរ Hook", callback_data=encode_script_action(sid, ver, "hooks")),
            InlineKeyboardButton("✂️ កាត់ពាក្យឲ្យខ្លី", callback_data=encode_script_action(sid, ver, "shorten")),
        ],
        [
            InlineKeyboardButton("🔁 បង្កើតកំណែថ្មី", callback_data=encode_script_action(sid, ver, "regen")),
            InlineKeyboardButton("✏️ កែសំណើ", callback_data=encode_script_action(sid, ver, "edit_req")),
        ],
        [
            InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_failure_keyboard(request_id: str) -> InlineKeyboardMarkup:
    """
    Failure keyboard:
    🔄 សាកសំណើនេះម្ដងទៀត
    ✏️ កែសំណើ
    🏠 Menu
    """
    keyboard = [
        [InlineKeyboardButton("🔄 សាកសំណើនេះម្ដងទៀត", callback_data=encode_retry(request_id))],
        [
            InlineKeyboardButton("✏️ កែសំណើ", callback_data=encode_menu(f"edit_failed:{request_id}")),
            InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_ideas_keyboard(batch_token: str, idea_count: int = 3) -> InlineKeyboardMarkup:
    """
    Ideas keyboard (never attaches script-refinement actions):
    ① យកគំនិតទី១
    ② យកគំនិតទី២
    ③ យកគំនិតទី៣
    ⬅️ ត្រឡប់ក្រោយ
    🏠 Menu
    """
    buttons = []
    labels = ["① យកគំនិតទី១", "② យកគំនិតទី២", "③ យកគំនិតទី៣", "④ យកគំនិតទី៤", "⑤ យកគំនិតទី៥"]
    for idx in range(1, idea_count + 1):
        lbl = labels[idx - 1] if idx <= len(labels) else f"យកគំនិត {idx}"
        buttons.append(InlineKeyboardButton(lbl, callback_data=encode_idea_pick(batch_token, idx)))

    # Layout buttons in rows of 2 or 3
    keyboard = []
    if len(buttons) <= 3:
        keyboard.append(buttons)
    else:
        keyboard.append(buttons[:2])
        keyboard.append(buttons[2:4])
        if len(buttons) > 4:
            keyboard.append(buttons[4:])

    keyboard.append([
        InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data=encode_nav("back")),
        InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
    ])
    return InlineKeyboardMarkup(keyboard)

def get_hook_options_keyboard(options_token: str, hook_count: int = 3) -> InlineKeyboardMarkup:
    """Keyboard for selecting one of 3 alternative hooks."""
    keyboard = [
        [
            InlineKeyboardButton("🎣 យក Hook ទី ១", callback_data=encode_hook_pick(options_token, 1)),
            InlineKeyboardButton("🎣 យក Hook ទី ២", callback_data=encode_hook_pick(options_token, 2)),
        ],
        [
            InlineKeyboardButton("🎣 យក Hook ទី ៣", callback_data=encode_hook_pick(options_token, 3)),
        ],
        [
            InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data=encode_nav("back")),
            InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard(current_duration: str, is_subbed: bool) -> InlineKeyboardMarkup:
    """Settings menu keyboard."""
    sub_label = "🔕 បិទ Subscribe" if is_subbed else "🔔 បើក Subscribe"
    keyboard = [
        [
            InlineKeyboardButton(f"⏱️ រយៈពេលកំណត់: {current_duration}", callback_data=encode_setting("dur_menu")),
        ],
        [
            InlineKeyboardButton("🎙️ វាស់ល្បឿននិយាយ (Pace)", callback_data=encode_setting("pace")),
            InlineKeyboardButton(sub_label, callback_data=encode_setting("sub_toggle")),
        ],
        [
            InlineKeyboardButton("📊 ស្ថានភាពប្រព័ន្ធ (Status)", callback_data=encode_setting("status")),
            InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_default_duration_keyboard(current_dur: str) -> InlineKeyboardMarkup:
    def mark(d):
        return f"✅ {d}" if d == current_dur else d

    keyboard = [
        [
            InlineKeyboardButton(mark("60 វិនាទី"), callback_data=encode_setting("dur:60 វិនាទី")),
            InlineKeyboardButton(mark("2 នាទី"), callback_data=encode_setting("dur:2 នាទី")),
        ],
        [
            InlineKeyboardButton(mark("3 នាទី"), callback_data=encode_setting("dur:3 នាទី")),
            InlineKeyboardButton(mark("5 នាទី"), callback_data=encode_setting("dur:5 នាទី")),
        ],
        [
            InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data=encode_nav("back")),
            InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_comedy_styles_keyboard(draft: Draft) -> InlineKeyboardMarkup:
    """Comedy style selection keyboard."""
    styles = [
        ("everyday", "ជីវិតរស់នៅប្រចាំថ្ងៃ (Everyday)"),
        ("parody", "ការលេងត្រាប់តាម (Parody)"),
        ("drama", "រឿងតូចធ្វើរឿងធំ (Over-dramatic)"),
        ("sarcasm", "កំប្លែងឌឺដង/ចំអក (Sarcastic)"),
    ]
    keyboard = []
    for s_id, s_name in styles:
        keyboard.append([
            InlineKeyboardButton(s_name, callback_data=encode_comedy_style(draft.id, draft.revision, s_id))
        ])
    keyboard.append([
        InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data=encode_nav("back")),
        InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
    ])
    return InlineKeyboardMarkup(keyboard)

def get_comedy_actors_keyboard(draft: Draft) -> InlineKeyboardMarkup:
    """Comedy actor count selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("👤 តួអង្គ ១ នាក់ (លេង ២ តួ)", callback_data=encode_comedy_actors(draft.id, draft.revision, 1)),
            InlineKeyboardButton("👥 តួអង្គ ២ នាក់ (សន្ទនាគ្នា)", callback_data=encode_comedy_actors(draft.id, draft.revision, 2)),
        ],
        [
            InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data=encode_nav("back")),
            InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_processing_keyboard(request_id: str) -> InlineKeyboardMarkup:
    """Keyboard shown during generation allowing user to Cancel."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 បោះបង់សំណើ (Cancel)", callback_data=encode_cancel(request_id))]
    ])

def get_back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data=encode_nav("back")),
            InlineKeyboardButton("🏠 Menu", callback_data=encode_nav("home")),
        ]
    ])
