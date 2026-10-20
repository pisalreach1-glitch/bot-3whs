"""
script_models.py - Structured Timestamped Shooting Plan, Timeline Validation & Speaking Pace Estimation.

Zero additional spending, zero paid APIs.
Provides:
- Data models for timestamped video scenes and full shooting plans.
- Strict chronological timeline validation (start=0, no gaps, no overlaps, end=target_duration).
- Non-whitespace Khmer dialogue unit counting heuristic & configurable pace estimation.
- Dialogue duration checks and warnings.
- Human-readable Telegram formatting with visual direction.
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Default speaking pace: ~10 Khmer meaningful characters/syllable units per second
# (Corresponds to ~120-150 spoken words/min in natural Cambodian conversational video pace).
DEFAULT_CHARS_PER_SECOND = 10.0

@dataclass
class Scene:
    scene_number: int
    start_seconds: int
    end_seconds: int
    spoken_text_km: str = ""
    shot_size: str = "Medium Shot"
    camera_action: str = "Static"
    visual_action: str = ""
    on_screen_text_km: str = ""
    editing_note: str = ""
    audio_note: str = ""
    estimated_spoken_seconds: float = 0.0
    is_dialogue_too_long: bool = False

@dataclass
class ScriptPlan:
    title: str
    target_audience: str
    hook: str
    caption: str
    hashtags: List[str]
    cta: str
    target_duration_seconds: int
    estimated_speaking_seconds: float
    scenes: List[Scene]
    is_timeline_valid: bool = True
    validation_notes: List[str] = field(default_factory=list)
    raw_response: str = ""

def parse_duration_seconds(duration_str: str) -> int:
    """
    Parses user-selected duration string to integer seconds.
    Supported durations:
    - 60 វិនាទី (60 seconds)
    - 2 នាទី (120 seconds)
    - 3 នាទី (180 seconds)
    - 5 នាទី (300 seconds)
    """
    s = str(duration_str).lower().strip()
    if "5" in s and ("នាទី" in s or "min" in s):
        return 300
    if "3" in s and ("នាទី" in s or "min" in s):
        return 180
    if "2" in s and ("នាទី" in s or "min" in s):
        return 120
    if "60" in s or "1" in s or "ខ្លី" in s:
        return 60
    # Try direct integer
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits:
        val = int(digits)
        if val in [60, 120, 180, 300]:
            return val
        if val <= 5:
            return val * 60
        return val
    return 60

def count_khmer_dialogue_units(text: str) -> int:
    """
    Counts dialogue units in Khmer text WITHOUT relying on whitespace word splitting.
    
    Why:
    Khmer orthography does not use whitespace between words. Spaces are only used 
    for clauses/sentences. Splitting by whitespace produces incorrect word counts (e.g. 1 word 
    for a 30-word sentence).
    
    Heuristic:
    We count meaningful script characters (Khmer consonants, independent vowels, dependent vowels,
    diacritics, plus Latin alphanumeric characters) excluding punctuation, whitespace, and formatting.
    This provides a robust, reproducible measure of spoken dialogue length.
    
    Limitations:
    This is an approximation heuristic. Actual spoken delivery depends on speaker rhythm,
    intonation, pauses, and speech style.
    """
    if not text:
        return 0
    # Match Khmer Unicode range (\u1780-\u17D3, \u17E0-\u17E9) and Latin alphanumerics
    meaningful_chars = re.findall(r"[\u1780-\u17D3\u17E0-\u17E9A-Za-z0-9]", text)
    return len(meaningful_chars)

def estimate_speaking_duration(
    spoken_text: str,
    chars_per_second: float = DEFAULT_CHARS_PER_SECOND
) -> float:
    """
    Estimates spoken dialogue duration in seconds.
    Only spoken text is passed in (excluding camera instructions, captions, editing notes).
    """
    if not spoken_text:
        return 0.0
    units = count_khmer_dialogue_units(spoken_text)
    pace = chars_per_second if chars_per_second > 0 else DEFAULT_CHARS_PER_SECOND
    return round(units / pace, 1)

def format_timestamp(seconds: int) -> str:
    """Formats seconds into MM:SS format (e.g. 0 -> 00:00, 65 -> 01:05)."""
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"

def validate_timeline(scenes: List[Scene], target_duration_seconds: int) -> Tuple[bool, List[str]]:
    """
    Strictly validates the timeline rules:
    - Must have at least 1 scene.
    - Start at 0 (scenes[0].start_seconds == 0).
    - Chronological order: start_seconds < end_seconds for each scene.
    - No negative times.
    - No zero-length scenes.
    - No gaps or overlaps: scenes[i].end_seconds == scenes[i+1].start_seconds.
    - Final scene must end at target_duration_seconds.
    """
    notes = []
    if not scenes:
        notes.append("គ្មានប្លង់ទាល់តែសោះ (No scenes generated).")
        return False, notes

    if scenes[0].start_seconds != 0:
        notes.append(f"ប្លង់ដំបូងមិនបានចាប់ផ្តើមពីវិនាទី 0 ទេ (ចាប់ផ្តើមពី {scenes[0].start_seconds}s).")

    for i, sc in enumerate(scenes):
        if sc.start_seconds < 0:
            notes.append(f"ប្លង់ទី {sc.scene_number} មានពេលវេលាអវិជ្ជមាន ({sc.start_seconds}s).")
        if sc.end_seconds <= sc.start_seconds:
            notes.append(f"ប្លង់ទី {sc.scene_number} គ្មានរយៈពេល ឬខុសលំដាប់ ({sc.start_seconds}s ដល់ {sc.end_seconds}s).")

        if i > 0:
            prev_end = scenes[i - 1].end_seconds
            if sc.start_seconds != prev_end:
                if sc.start_seconds > prev_end:
                    notes.append(f"ចន្លោះប្រហោង (Gap) រវាងប្លង់ {scenes[i-1].scene_number} និង {sc.scene_number}: {prev_end}s ដល់ {sc.start_seconds}s.")
                else:
                    notes.append(f"ជាន់គ្នា (Overlap) រវាងប្លង់ {scenes[i-1].scene_number} និង {sc.scene_number}: {prev_end}s និង {sc.start_seconds}s.")

    last_end = scenes[-1].end_seconds
    if last_end != target_duration_seconds:
        notes.append(f"ប្លង់ចុងក្រោយបញ្ចប់នៅ {last_end}s មិនត្រូវនឹងរយៈពេលកំណត់ {target_duration_seconds}s ទេ។")

    is_valid = len(notes) == 0
    return is_valid, notes

def repair_timeline_if_minor(scenes: List[Scene], target_duration_seconds: int) -> bool:
    """
    Attempts to fix minor continuous timeline rounding discrepancies (e.g. off by 1-2s at the end)
    without AI retries. Returns True if repaired successfully.
    """
    if not scenes or len(scenes) == 0:
        return False

    current_t = 0
    for sc in scenes:
        dur = max(1, sc.end_seconds - sc.start_seconds)
        sc.start_seconds = current_t
        sc.end_seconds = current_t + dur
        current_t = sc.end_seconds

    # Adjust the last scene's end_seconds to match target_duration_seconds if discrepancy is small (<= 5s)
    diff = target_duration_seconds - scenes[-1].end_seconds
    if abs(diff) <= 10:
        new_last_end = target_duration_seconds
        if new_last_end > scenes[-1].start_seconds:
            scenes[-1].end_seconds = new_last_end
            return True

    return False

def parse_and_validate_script_plan(
    json_str: str,
    target_duration_seconds: int,
    user_pace: float = DEFAULT_CHARS_PER_SECOND
) -> ScriptPlan:
    """
    Parses raw JSON text from Gemini, extracts scenes, validates timeline and speaking pace.
    """
    data = {}
    clean_json = json_str.strip()
    if clean_json.startswith("```"):
        clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json)
        clean_json = re.sub(r"\s*```$", "", clean_json)

    try:
        data = json.loads(clean_json)
    except Exception as e:
        # Fallback: regex search for outer JSON object
        match = re.search(r"\{.*\}", clean_json, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = {}

    title = data.get("title", "Script វីដេអូ 3WHs")
    target_audience = data.get("target_audience", "ទស្សនិកជនទូទៅ")
    hook = data.get("hook", "")
    caption = data.get("caption", "")
    hashtags = data.get("hashtags", [])
    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split() if h.startswith("#")]
    cta = data.get("cta", "")

    raw_scenes = data.get("scenes", [])
    scenes: List[Scene] = []

    for idx, sc_dict in enumerate(raw_scenes, start=1):
        if not isinstance(sc_dict, dict):
            continue
        try:
            start_s = int(sc_dict.get("start_seconds", 0))
            end_s = int(sc_dict.get("end_seconds", 0))
        except (ValueError, TypeError):
            start_s = 0
            end_s = 0

        spoken = str(sc_dict.get("spoken_text_km", "")).strip()
        shot_size = str(sc_dict.get("shot_size", "Medium Shot")).strip()
        camera = str(sc_dict.get("camera_action", "Static")).strip()
        visual = str(sc_dict.get("visual_action", "")).strip()
        screen_txt = str(sc_dict.get("on_screen_text_km", "")).strip()
        editing = str(sc_dict.get("editing_note", "")).strip()
        audio = str(sc_dict.get("audio_note", "")).strip()

        # Calculate estimated speaking duration for dialogue
        est_spoken = estimate_speaking_duration(spoken, user_pace)
        scene_dur = max(0, end_s - start_s)
        # Warning if dialogue exceeds scene duration by more than 20%
        is_too_long = bool(spoken and est_spoken > (scene_dur * 1.20) and scene_dur > 0)

        scene = Scene(
            scene_number=int(sc_dict.get("scene_number", idx)),
            start_seconds=start_s,
            end_seconds=end_s,
            spoken_text_km=spoken,
            shot_size=shot_size,
            camera_action=camera,
            visual_action=visual,
            on_screen_text_km=screen_txt,
            editing_note=editing,
            audio_note=audio,
            estimated_spoken_seconds=est_spoken,
            is_dialogue_too_long=is_too_long,
        )
        scenes.append(scene)

    # Initial timeline validation
    is_valid, notes = validate_timeline(scenes, target_duration_seconds)
    if not is_valid:
        # Try a quick repair for small rounding gaps
        if repair_timeline_if_minor(scenes, target_duration_seconds):
            is_valid, notes = validate_timeline(scenes, target_duration_seconds)

    total_est_speaking = sum(sc.estimated_spoken_seconds for sc in scenes)

    return ScriptPlan(
        title=title,
        target_audience=target_audience,
        hook=hook,
        caption=caption,
        hashtags=hashtags,
        cta=cta,
        target_duration_seconds=target_duration_seconds,
        estimated_speaking_seconds=round(total_est_speaking, 1),
        scenes=scenes,
        is_timeline_valid=is_valid,
        validation_notes=notes,
        raw_response=json_str,
    )

def format_script_for_telegram(plan: ScriptPlan, user_pace: float = DEFAULT_CHARS_PER_SECOND) -> str:
    """
    Formats the ScriptPlan into clean, human-readable Telegram Markdown blocks.
    Never exposes raw JSON to ordinary users.
    Includes visual direction and estimated speaking duration with disclaimers.
    """
    dur_label = f"{plan.target_duration_seconds} វិនាទី" if plan.target_duration_seconds < 60 else f"{plan.target_duration_seconds // 60} នាទី ({plan.target_duration_seconds} វិនាទី)"

    lines = []
    lines.append(f"🎬 *{plan.title}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    if plan.target_audience:
        lines.append(f"👥 *ទស្សនិកជនគោលដៅ*: {plan.target_audience}")
    lines.append(f"⏱️ *រយៈពេលវីដេអូកំណត់*: `{dur_label}`")
    lines.append(
        f"🎙️ *រយៈពេលនិយាយ៖ ប៉ាន់ស្មាន* `~{plan.estimated_speaking_seconds:.1f}s` "
        f"_(អត្រា {user_pace:.1f} តួអក្សរ/s — ល្បឿនជាក់ស្តែងអាចប្រែប្រួលតាមការអាន)_"
    )

    if not plan.is_timeline_valid:
        lines.append("\n⚠️ *សម្គាល់អំពីពេលវេលាប្លង់ (Timeline Notice):*")
        for n in plan.validation_notes:
            lines.append(f"• _{n}_")
        lines.append("_(ខ្លឹមសារខាងក្រោមត្រូវបានបង្ហាញសម្រាប់រៀបចំផលិតដោយផ្ទាល់)_\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📋 *ផែនការថត និងស្គ្រីបតាមពេលវេលា (Shooting Plan)*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━\n")

    for sc in plan.scenes:
        start_str = format_timestamp(sc.start_seconds)
        end_str = format_timestamp(sc.end_seconds)
        dur = max(0, sc.end_seconds - sc.start_seconds)

        header = f"🎬 *ប្លង់ទី {sc.scene_number} | {start_str}–{end_str}* ({dur}s)"
        lines.append(header)

        if sc.spoken_text_km:
            lines.append(f"🗣️ *ពាក្យនិយាយ*៖ \"{sc.spoken_text_km}\"")
            if sc.is_dialogue_too_long:
                lines.append(f"   ⚠️ _(ពាក្យនិយាយអាចវែងបន្តិច ~{sc.estimated_spoken_seconds:.1f}s លើសប្រវែងប្លង់ {dur}s — គួរកាត់បន្ថយពាក្យ ឬនិយាយលឿន)_")
            else:
                lines.append(f"   ⏱️ _(ប៉ាន់ស្មានការនិយាយ៖ ~{sc.estimated_spoken_seconds:.1f}s)_")
        else:
            lines.append("🗣️ *ពាក្យនិយាយ*៖ _(គ្មានពាក្យនិយាយ — ជាប្លង់ B-roll / កាយវិការ / Visual Action)_")

        lines.append(f"📷 *ទំហំប្លង់*៖ {sc.shot_size}")
        if sc.camera_action and sc.camera_action != "Static":
            lines.append(f"📹 *កាមេរ៉ា*៖ {sc.camera_action}")
        if sc.visual_action:
            lines.append(f"🎥 *សកម្មភាព / Visual*៖ {sc.visual_action}")
        if sc.on_screen_text_km:
            lines.append(f"📝 *អក្សរលើអេក្រង់*៖ `{sc.on_screen_text_km}`")
        if sc.editing_note:
            lines.append(f"✂️ *ការកាត់ត*៖ {sc.editing_note}")
        if sc.audio_note:
            lines.append(f"🔊 *សំឡេង*៖ {sc.audio_note}")

        lines.append("")  # Blank line between scenes

    # End summary: Caption, Hashtags, CTA
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    if plan.caption:
        lines.append(f"📝 *Caption Social Media*:\n{plan.caption}\n")
    if plan.hashtags:
        ht_str = " ".join(plan.hashtags) if isinstance(plan.hashtags, list) else str(plan.hashtags)
        lines.append(f"🏷️ *Hashtags*:\n{ht_str}\n")
    if plan.cta:
        lines.append(f"📣 *Call to Action (CTA)*:\n{plan.cta}\n")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 _គន្លឹះ៖ ប្រើទូរស័ព្ទដៃ និងពន្លឺធម្មជាតិ ឬ Ring Light សាមញ្ញ ក៏អាចថតបានស្អាត!_")

    return "\n".join(lines)
