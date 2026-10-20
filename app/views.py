"""
app/views.py - Khmer Text Rendering for Screens, Script Views, and Dialogues.

Renders directly from validated ScriptPlan and domain models.
Never displays raw JSON or tracebacks.
"""

from typing import List, Optional
from app.models import Draft, SavedScript, Idea, EvidenceRecord
from script_models import ScriptPlan, Scene, format_timestamp

FORMAT_NAMES = {
    "3whs": "🎬 3WHs Hook Script",
    "pov": "🎭 POV / Storytelling",
    "myth": "⚡ Myth vs Reality",
    "transform": "🔄 Before & After",
    "hottake": "🌶️ Hot Take / Opinion",
    "toplist": "📋 Top List / Ranking",
    "comedy": "😂 Short Comedy Video",
}

def render_welcome(current_duration: str) -> str:
    return (
        "👋 *សួស្តី! ខ្ញុំជា 3WHs AI Video Assistant* 🤖\n"
        "ជំនួយការផលិត Script វីដេអូខ្លី (TikTok / Reels / Shorts) អាជីព!\n\n"
        f"⏱️ *រយៈពេលកំណត់បច្ចុប្បន្ន:* `{current_duration}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ *សូមជ្រើសរើសមុខងារដែលអ្នកចង់ប្រើប្រាស់៖*\n"
        "• ចុច **[🎬 បង្កើត Script]** ដើម្បីរើស Format និងវាយប្រធានបទ\n"
        "• ចុច **[😂 បង្កើតកំប្លែង]** សម្រាប់ Script កំប្លែងខ្លីៗ\n"
        "• ចុច **[💡 រកគំនិតមាតិកា]** ដើម្បីមើលព័ត៌មាន និងគំនិតថ្មីៗ"
    )

def render_format_selection() -> str:
    return (
        "🎬 *ជ្រើសរើសទម្រង់មាតិកា (Format)*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "សូមជ្រើសរើសទម្រង់វីដេអូដែលអ្នកចង់ផលិតខាងក្រោម៖"
    )

def render_topic_prompt(format_id: str) -> str:
    fmt_name = FORMAT_NAMES.get(format_id, "Script")
    return (
        f"📝 *សូមបញ្ចូលប្រធានបទសម្រាប់ {fmt_name}*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "សូមវាយប្រធានបទ គំនិត ឬវិស័យអាជីវកម្មរបស់អ្នករួចផ្ញើមកកាន់ Bot៖\n\n"
        "_ឧទាហរណ៍៖_\n"
        "• «វិធីរើសខោខូវប៊យឱ្យសមរាង»\n"
        "• «គន្លឹះសន្សំប្រាក់សម្រាប់អ្នកធ្វើការ»\n"
        "• «ហេតុអ្វីហាត់ប្រាណមិនស្រកទម្ងន់»\n"
        "• «របៀបឆុងកាហ្វេ Cold Brew ខ្លួនឯង»\n\n"
        "💡 _អ្នកអាចចុច ⬅️ ត្រឡប់ក្រោយ ឬ /cancel ដើម្បីបោះបង់!_"
    )

def render_review(draft: Draft, pace: float) -> str:
    fmt_name = FORMAT_NAMES.get(draft.format_id, draft.format_id)
    dur_label = f"{draft.duration_seconds} វិនាទី" if draft.duration_seconds < 60 else f"{draft.duration_seconds // 60} នាទី ({draft.duration_seconds} វិនាទី)"

    lines = [
        "📋 *ផ្ទៀងផ្ទាត់ព័ត៌មានសំណើ (Draft Review)*",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"• 🎬 **ទម្រង់មាតិកា**: {fmt_name}",
        f"• 📝 **ប្រធានបទ**: {draft.topic}",
        f"• ⏱️ **រយៈពេលវីដេអូ**: `{dur_label}`",
        f"• 🎙️ **ល្បឿននិយាយគិតទុក**: `{pace:.1f} តួអក្សរ/វិនាទី`",
    ]
    if draft.comedy_style:
        lines.append(f"• 😂 **ស្ទីលកំប្លែង**: {draft.comedy_style}")
    if draft.actor_count:
        lines.append(f"• 👥 **ចំនួនតួអង្គ**: {draft.actor_count} នាក់")
    if draft.evidence_ids:
        lines.append(f"• 🔗 **យោងព័ត៌មានថ្មីៗ**: {len(draft.evidence_ids)} ប្រភព")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━",
        "👉 _ពិនិត្យព័ត៌មានខាងលើ រួចចុច **[✨ បង្កើត Script]** ដើម្បីឱ្យ AI រៀបចំផែនការថត!_",
    ])
    return "\n".join(lines)

def render_script_summary(script: SavedScript, pace: float) -> str:
    plan = script.plan
    dur_label = f"{plan.target_duration_seconds} វិនាទី" if plan.target_duration_seconds < 60 else f"{plan.target_duration_seconds // 60} នាទី ({plan.target_duration_seconds} វិនាទី)"

    lines = [
        f"🎬 *{plan.title}*",
        f"📌 _កំណែទី {script.version} (Version {script.version})_",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]
    if plan.target_audience:
        lines.append(f"👥 *ទស្សនិកជនគោលដៅ*: {plan.target_audience}")
    lines.append(f"⏱️ *រយៈពេលវីដេអូ*: `{dur_label}`")
    lines.append(
        f"🎙️ *រយៈពេលនិយាយប៉ាន់ស្មាន*: `~{plan.estimated_speaking_seconds:.1f}s` "
        f"_(ផ្អែកលើ {pace:.1f} តួអក្សរ/s)_"
    )

    if plan.validation_notes:
        for n in plan.validation_notes:
            lines.append(f"ℹ️ _{n}_")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━",
        f"🎬 **ចំនួនប្លង់សរុប**: {len(plan.scenes)} ប្លង់",
        "",
        "💡 _ជ្រើសរើសប៊ូតុងខាងក្រោមដើម្បីមើល៖_",
        "• **[📖 ពាក្យនិយាយ]** — អត្ថបទសម្រាប់អាននិយាយ",
        "• **[🎥 ប្លង់ថត]** — ផែនការកាមេរ៉ា និងសកម្មភាពលម្អិត",
        "• **[📝 Caption]** — Caption, Hashtags & CTA សម្រាប់ផុស",
    ])
    return "\n".join(lines)

def render_script_read(script: SavedScript) -> str:
    plan = script.plan
    lines = [
        f"📖 *ពាក្យនិយាយសុទ្ធ (Read View) — {plan.title}*",
        f"📌 _កំណែទី {script.version}_",
        "━━━━━━━━━━━━━━━━━━━━━\n",
    ]

    for sc in plan.scenes:
        start_str = format_timestamp(sc.start_seconds)
        end_str = format_timestamp(sc.end_seconds)
        dur = sc.end_seconds - sc.start_seconds

        lines.append(f"⏱️ *[{start_str}–{end_str}] ({dur}s)* — ប្លង់ទី {sc.scene_number}")
        if sc.spoken_text_km and sc.spoken_text_km.strip():
            lines.append(f"🗣️ \"{sc.spoken_text_km}\"")
        else:
            lines.append("🗣️ _(គ្មានពាក្យនិយាយ — B-roll / កាយវិការ / សកម្មភាព)_")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 _ព័ត៌មានប៉ាន់ស្មាន៖ សូមអានសាកល្បងជាមួយនាឡិកាវាស់ម៉ោងជាក់ស្តែងមុនពេលថត!_")
    return "\n".join(lines)

def render_script_shots(script: SavedScript, pace: float) -> str:
    plan = script.plan
    lines = [
        f"🎥 *ផែនការថតលម្អិត (Shots View) — {plan.title}*",
        f"📌 _កំណែទី {script.version}_",
        "━━━━━━━━━━━━━━━━━━━━━\n",
    ]

    for sc in plan.scenes:
        start_str = format_timestamp(sc.start_seconds)
        end_str = format_timestamp(sc.end_seconds)
        dur = max(0, sc.end_seconds - sc.start_seconds)

        lines.append(f"🎬 *ប្លង់ទី {sc.scene_number} | {start_str}–{end_str}* ({dur}s)")
        if sc.spoken_text_km and sc.spoken_text_km.strip():
            lines.append(f"🗣️ *ពាក្យនិយាយ*: \"{sc.spoken_text_km}\"")
            if sc.is_dialogue_too_long:
                lines.append(f"   ⚠️ _(ពាក្យនិយាយអាចវែងបន្តិច ~{sc.estimated_spoken_seconds:.1f}s លើសប្រវែងប្លង់ {dur}s)_")
            else:
                lines.append(f"   ⏱️ _(ប៉ាន់ស្មានការនិយាយ៖ ~{sc.estimated_spoken_seconds:.1f}s)_")
        else:
            lines.append("🗣️ *ពាក្យនិយាយ*: _(Visual-only / B-roll)_")

        lines.append(f"📷 *ទំហំប្លង់*: {sc.shot_size}")
        if sc.camera_action and sc.camera_action != "Static":
            lines.append(f"📹 *កាមេរ៉ា*: {sc.camera_action}")
        if sc.visual_action:
            lines.append(f"🎥 *សកម្មភាព*: {sc.visual_action}")
        if sc.on_screen_text_km:
            lines.append(f"📝 *អក្សរលើអេក្រង់*: `{sc.on_screen_text_km}`")
        if sc.editing_note:
            lines.append(f"✂️ *ការកាត់ត*: {sc.editing_note}")
        if sc.audio_note:
            lines.append(f"🔊 *សំឡេង*: {sc.audio_note}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

def render_script_caption(script: SavedScript) -> str:
    plan = script.plan
    lines = [
        f"📝 *Caption Social Media — {plan.title}*",
        f"📌 _កំណែទី {script.version}_",
        "━━━━━━━━━━━━━━━━━━━━━\n",
    ]
    if plan.caption:
        lines.append(f"📝 *Caption*:\n{plan.caption}\n")
    if plan.hashtags:
        ht_str = " ".join(plan.hashtags) if isinstance(plan.hashtags, list) else str(plan.hashtags)
        lines.append(f"🏷️ *Hashtags*:\n`{ht_str}`\n")
    if plan.cta:
        lines.append(f"📣 *Call to Action (CTA)*:\n{plan.cta}\n")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

def render_hook_options(script: SavedScript, hooks: List[dict]) -> str:
    lines = [
        "🎣 *ជម្រើស Hook ថ្មីទាំង ៣ បែប*",
        f"📜 _សម្រាប់ Script: {script.plan.title} (កំណែ {script.version})_",
        "━━━━━━━━━━━━━━━━━━━━━\n",
    ]
    for idx, h in enumerate(hooks, start=1):
        lines.append(f"✨ *ជម្រើសទី {idx} ({h.get('type', 'Hook')}):*")
        lines.append(f"🗣️ *ពាក្យនិយាយ*: \"{h.get('spoken_text', '')}\"")
        if h.get('visual'):
            lines.append(f"🎥 *Visual/កាយវិការ*: {h.get('visual')}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("👉 _ជ្រើសរើសប៊ូតុងខាងក្រោមដើម្បីអនុវត្ត Hook ថ្មីជំនួសប្លង់ទី ១ ក្នុង Script របស់អ្នក!_")
    return "\n".join(lines)

def render_ideas_batch(ideas: List[Idea], evidence: List[EvidenceRecord], category: str) -> str:
    lines = [
        f"💡 *គំនិតមាតិកាវីដេអូ — វិស័យ {category}*",
        "━━━━━━━━━━━━━━━━━━━━━\n",
    ]
    for i in ideas:
        lines.append(f"🔥 **គំនិតទី {i.id}៖ {i.topic}**")
        lines.append(f"• 🎯 **Hook**: {i.hook}")
        lines.append(f"• 📋 **Format ណែនាំ**: {FORMAT_NAMES.get(i.suggested_format, i.suggested_format)}")
        if i.source_ids:
            refs = ", ".join(f"[{sid}]" for sid in i.source_ids)
            lines.append(f"• 🔗 **យោងព័ត៌មានលេខ**: {refs}")
        lines.append("")

    if evidence:
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🔗 **ប្រភពព័ត៌មានថ្មីៗដែលបានយោង (Verified Sources):**")
        for ev in evidence:
            pub_date = ev.published_at.strftime("%d/%m/%Y") if ev.published_at else "ថ្មីៗ"
            lines.append(f"• [{ev.id}] [{ev.publisher}: {ev.title}]({ev.url}) — _{pub_date}_")
        lines.append("\n💡 _(ផ្អែកលើព័ត៌មានសាធារណៈក្នុងរយៈពេល ៤៨ ម៉ោងចុងក្រោយ មិនមែនទិន្នន័យ Trend TikTok/FB ឡើយ)_")
    else:
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append("ℹ️ _(គំនិតទូទៅពី AI — មិនបានផ្ទៀងផ្ទាត់ជាមួយព័ត៌មានថ្មីៗ)_")

    lines.append("\n👉 _ចុចប៊ូតុង **[①/②/③ យកគំនិត...]** ខាងក្រោមដើម្បីយកប្រធានបទទៅបង្កើត Script!_")
    return "\n".join(lines)

def render_settings(current_duration: str, pace: float, is_subbed: bool) -> str:
    return (
        "⚙️ *ការកំណត់ Bot (Settings)*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"• ⏱️ **រយៈពេលកំណត់ទូទៅ**: `{current_duration}`\n"
        f"• 🎙️ **ល្បឿននិយាយប៉ាន់ស្មាន**: `{pace:.1f} តួអក្សរ/វិនាទី`\n"
        f"• 🔔 **ទទួលគំនិតប្រចាំថ្ងៃ (08:00)**: {'✅ បើកដំណើរការ' if is_subbed else '❌ មិនទាន់បើក'}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "_សូមជ្រើសរើសមុខងារដែលអ្នកចង់កែសម្រួលខាងក្រោម៖_"
    )

def render_pace_sample_instruction(sample_text: str) -> str:
    return (
        "🎙️ *ការវាស់ល្បឿននិយាយផ្ទាល់ខ្លួន (Speaking Pace Calibration)*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "សូមអានអត្ថបទគំរូជាភាសាខ្មែរខាងក្រោម ដោយប្រើកម្មវិធីកំណត់ម៉ោង (Timer) នៅលើទូរស័ព្ទរបស់អ្នក៖\n\n"
        f"📝 *អត្ថបទគំរូ៖*\n_«{sample_text}»_\n\n"
        "👉 **បន្ទាប់ពីអានចប់ សូមវាយបញ្ចូលតែចំនួនវិនាទី (Seconds) ប៉ុណ្ណោះផ្ញើមកវិញ**\n"
        "_(ឧទាហរណ៍៖ `12` ឬ `15.5`)_\n\n"
        "💡 _ចំណាំ៖ ការគណនាផ្អែកលើចំនួនតួអក្សរខ្មែរ (Character Units) សម្រាប់ប៉ាន់ស្មានប្រហាក់ប្រហែលប៉ុណ្ណោះ!_"
    )

def render_failure(error_code: str, user_message_km: str) -> str:
    return (
        f"⚠️ *សំណើមិនទាន់ជោគជ័យ (Code: {error_code})*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{user_message_km}\n\n"
        "🔄 _Script ចាស់ដែលជោគជ័យរបស់អ្នកត្រូវបានរក្សាទុកដដែលដោយសុវត្ថិភាព។_\n"
        "👉 សូមចុចប៊ូតុង **[🔄 សាកសំណើនេះម្ដងទៀត]** ឬកែប្រែសំណើរបស់អ្នក!"
    )

def render_help() -> str:
    return (
        "📖 *ការណែនាំ និងពាក្យបញ្ជា Bot (Help)*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 /start — បង្ហាញ Menu ដើម និងជ្រើសរើស Format\n"
        "🔹 /cancel — បោះបង់សំណើបច្ចុប្បន្នភ្លាមៗ\n"
        "🔹 /ideas [វិស័យ] — រកគំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ\n"
        "🔹 /pace <វិនាទី> <អត្ថបទ> — វាស់ និងកំណត់ល្បឿននិយាយផ្ទាល់ខ្លួន\n"
        "🔹 /status — ពិនិត្យស្ថានភាពប្រព័ន្ធ និង API\n"
        "🔹 /subscribe — បើកការទទួលគំនិតមាតិការៀងរាល់ព្រឹក\n"
        "🔹 /unsubscribe — បិទការទទួលគំនិតមាតិកា\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 _គ្រាន់តែចុច /start រួចជ្រើសរើសប៊ូតុងគឺងាយស្រួលបំផុត!_"
    )
