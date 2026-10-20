"""
script_models.py - Structured Timestamped Shooting Plan, Timeline Validation & Speaking Pace Estimation.

Zero additional spending, zero paid APIs.
Provides:
- Strict typed validation for JSON schema, field types, and scene entries.
- Strict chronological timeline validation (start=0, no gaps, no overlaps, exact duration).
- Narrow documented rounding tolerance for continuous timelines (<= 1s at final scene).
- Non-whitespace Khmer character unit counting heuristic & configurable pace estimation.
- Dialogue duration checks and warnings.
- Explicit PlanResult contract and human-readable Telegram formatting with visual direction.
"""

import math
import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Default speaking pace: ~10 Khmer meaningful script characters per second
# Note: This is an empirical character-unit approximation heuristic for conversational speech.
# It does NOT represent a universal words-per-minute rate. Actual speech delivery varies.
DEFAULT_CHARS_PER_SECOND = 10.0
DEFAULT_PAUSE_PER_SCENE = 0.0  # Explicit pause allowance between scenes in seconds

class ValidationError(Exception):
    """Raised when JSON schema, field types, or timeline validation fails."""
    pass

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

@dataclass
class PlanResult:
    """Explicit success/failure contract for script generation & refinements."""
    success: bool
    plan: Optional[ScriptPlan] = None
    formatted_text: str = ""
    error_message: Optional[str] = None
    validation_notes: List[str] = field(default_factory=list)

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
    Counts dialogue units in Khmer text using character units, WITHOUT relying on whitespace word splitting.
    
    Why:
    Khmer orthography does not use whitespace between words. Spaces separate phrases/clauses.
    Splitting by whitespace produces incorrect word counts (e.g. 1 word for a 30-word sentence).
    
    Heuristic:
    We count meaningful script characters (Khmer consonants, independent vowels, dependent vowels,
    diacritics, plus Latin alphanumeric characters) excluding whitespace and punctuation.
    
    Limitations:
    This is an approximation heuristic based on character counts, not an exact syllable or word count.
    It does not measure audio speech directly.
    """
    if not text or not isinstance(text, str):
        return 0
    meaningful_chars = re.findall(r"[\u1780-\u17D3\u17E0-\u17E9A-Za-z0-9]", text)
    return len(meaningful_chars)

def estimate_speaking_duration(
    spoken_text: str,
    chars_per_second: float = DEFAULT_CHARS_PER_SECOND,
    pause_allowance: float = DEFAULT_PAUSE_PER_SCENE
) -> float:
    """
    Estimates spoken dialogue duration in seconds.
    Only spoken dialogue text is estimated; visual-only scenes return 0.0s.
    """
    if not spoken_text or not isinstance(spoken_text, str) or not spoken_text.strip():
        return 0.0
    units = count_khmer_dialogue_units(spoken_text)
    if units == 0:
        return 0.0
    pace = chars_per_second if chars_per_second > 0 else DEFAULT_CHARS_PER_SECOND
    speech_time = units / pace
    return round(speech_time + pause_allowance, 1)

def format_timestamp(seconds: int) -> str:
    """Formats seconds into MM:SS format (e.g. 0 -> 00:00, 65 -> 01:05)."""
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"

def _validate_integer_timestamp(val: Any, field_name: str, scene_idx: int) -> int:
    """
    Strictly validates timestamp fields (start_seconds, end_seconds).
    Rejects booleans, None, non-finite numbers (NaN/inf), and fractional timestamps.
    Does NOT silently truncate with int().
    """
    if isinstance(val, bool) or val is None:
        raise ValidationError(f"ប្លង់ទី {scene_idx}: {field_name} មិនអាចជា boolean ឬ null បានឡើយ")
    if isinstance(val, int):
        if val < 0:
            raise ValidationError(f"ប្លង់ទី {scene_idx}: {field_name} មិនអាចជាពេលវេលាអវិជ្ជមានឡើយ ({val}s)")
        return val
    if isinstance(val, float):
        if not math.isfinite(val):
            raise ValidationError(f"ប្លង់ទី {scene_idx}: {field_name} មិនអាចជា NaN ឬ Infinity ឡើយ")
        if not val.is_integer():
            raise ValidationError(f"ប្លង់ទី {scene_idx}: {field_name} ត្រូវតែជាចំនួនគត់វិនាទី (មិនអាចជាទសភាគ {val} ឡើយ)")
        int_val = int(val)
        if int_val < 0:
            raise ValidationError(f"ប្លង់ទី {scene_idx}: {field_name} មិនអាចជាពេលវេលាអវិជ្ជមានឡើយ ({int_val}s)")
        return int_val
    if isinstance(val, str) and val.strip().isdigit():
        return int(val.strip())
    raise ValidationError(f"ប្លង់ទី {scene_idx}: {field_name} មានតម្លៃមិនត្រឹមត្រូវ ({val})")

def _validate_string_field(val: Any, field_name: str, scene_idx: Optional[int] = None, allow_empty: bool = True) -> str:
    """
    Strictly validates string fields.
    Does NOT silently convert arbitrary objects to strings.
    """
    prefix = f"ប្លង់ទី {scene_idx}: " if scene_idx is not None else ""
    if val is None:
        if allow_empty:
            return ""
        raise ValidationError(f"{prefix}{field_name} មិនអាចជា null ឡើយ")
    if not isinstance(val, str):
        raise ValidationError(f"{prefix}{field_name} ត្រូវតែជា string (មិនអាចជា {type(val).__name__} ឡើយ)")
    s = val.strip()
    if not allow_empty and not s:
        raise ValidationError(f"{prefix}{field_name} មិនអាចទទេបានឡើយ")
    return s

def validate_and_build_plan(
    raw_json_str: str,
    target_duration_seconds: int,
    user_pace: float = DEFAULT_CHARS_PER_SECOND
) -> PlanResult:
    """
    Strict validation pipeline:
    1. Parse JSON safely (reject syntax error, non-dict top levels).
    2. Validate required metadata and field types.
    3. Validate scenes list (non-empty, dict entries, integer scene_number, valid timestamps, valid visual fields).
    4. Validate timeline continuity (starts at 0, strictly consecutive, no gaps, no overlaps, end=target_duration).
    5. Allow narrow documented rounding tolerance on end-time only (<= 1s at final scene of continuous timeline).
    6. Recalculate speaking estimates and warnings.
    Returns: PlanResult with success flag, plan, and formatted text or clear error.
    """
    if not raw_json_str or not isinstance(raw_json_str, str) or not raw_json_str.strip():
        return PlanResult(
            success=False,
            error_message="ទិន្នន័យ Script ពី AI គឺទទេ (Empty response from AI).",
            formatted_text="⚠️ *ការបង្កើត Script មិនជោគជ័យ៖* មិនទទួលបានទិន្នន័យពី AI ឡើយ។ សូមសាកល្បងម្ដងទៀត!"
        )

    clean_json = raw_json_str.strip()
    if clean_json.startswith("```"):
        clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json)
        clean_json = re.sub(r"\s*```$", "", clean_json)

    try:
        data = json.loads(clean_json)
    except Exception:
        # Fallback: extract outermost JSON object { ... }
        match = re.search(r"\{.*\}", clean_json, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception as e:
                return PlanResult(
                    success=False,
                    error_message=f"ទម្រង់ JSON មិនត្រឹមត្រូវ: {e}",
                    formatted_text="⚠️ *ការបង្កើត Script មិនជោគជ័យ៖* ទម្រង់ JSON របស់ AI មិនត្រឹមត្រូវឡើយ។ សូមសាកល្បងបង្កើតម្ដងទៀត!"
                )
        else:
            return PlanResult(
                success=False,
                error_message="មិនអាចស្វែងរក JSON Object ក្នុងចម្លើយរបស់ AI ឡើយ",
                formatted_text="⚠️ *ការបង្កើត Script មិនជោគជ័យ៖* ទម្រង់ទិន្នន័យពី AI មិនត្រឹមត្រូវឡើយ។ សូមចុច [🔁 បង្កើតម្ដងទៀត]!"
            )

    # 1. Top-level must be a dictionary
    if not isinstance(data, dict):
        return PlanResult(
            success=False,
            error_message=f"Top-level JSON ត្រូវតែជា Object មិនមែនជា {type(data).__name__} ឡើយ",
            formatted_text="⚠️ *ការបង្កើត Script មិនជោគជ័យ៖* ទិន្នន័យ AI មិនមែនជាទម្រង់ Script Object ត្រឹមត្រូវឡើយ។"
        )

    try:
        title = _validate_string_field(data.get("title"), "title", allow_empty=False)
    except ValidationError:
        title = "Script វីដេអូ 3WHs"

    try:
        target_audience = _validate_string_field(data.get("target_audience", ""), "target_audience", allow_empty=True)
        hook = _validate_string_field(data.get("hook", ""), "hook", allow_empty=True)
        caption = _validate_string_field(data.get("caption", ""), "caption", allow_empty=True)
        cta = _validate_string_field(data.get("cta", ""), "cta", allow_empty=True)

        raw_hashtags = data.get("hashtags", [])
        if isinstance(raw_hashtags, list):
            hashtags = []
            for h in raw_hashtags:
                if isinstance(h, str) and h.strip():
                    hashtags.append(h.strip() if h.strip().startswith("#") else f"#{h.strip()}")
        elif isinstance(raw_hashtags, str):
            hashtags = [h.strip() for h in raw_hashtags.split() if h.strip().startswith("#")]
        else:
            raise ValidationError(f"Hashtags ត្រូវតែជាបញ្ជី string មិនមែនជា {type(raw_hashtags).__name__} ឡើយ")

        # 2. Scenes validation
        if "scenes" not in data or not isinstance(data["scenes"], list):
            raise ValidationError("ទិន្នន័យខ្វះបញ្ជីប្លង់ (scenes) ឬ scenes មិនមែនជាបញ្ជី (list) ឡើយ")

        raw_scenes = data["scenes"]
        if len(raw_scenes) == 0:
            raise ValidationError("បញ្ជីប្លង់វីដេអូ (scenes) គឺទទេ គ្មានប្លង់ថតណាមួយត្រូវបានបង្កើតឡើយ")

        scenes: List[Scene] = []
        for idx, sc_dict in enumerate(raw_scenes, start=1):
            if not isinstance(sc_dict, dict):
                raise ValidationError(f"ប្លង់ទី {idx} មិនមែនជា Object ឡើយ (ជា {type(sc_dict).__name__})")

            # Validate scene_number
            sc_num_raw = sc_dict.get("scene_number", idx)
            if isinstance(sc_num_raw, bool) or not isinstance(sc_num_raw, int) or sc_num_raw <= 0:
                raise ValidationError(f"ប្លង់ទី {idx}: scene_number ត្រូវតែជាចំនួនគត់វិជ្ជមាន (មិនមែន {sc_num_raw})")

            start_s = _validate_integer_timestamp(sc_dict.get("start_seconds"), "start_seconds", idx)
            end_s = _validate_integer_timestamp(sc_dict.get("end_seconds"), "end_seconds", idx)

            spoken = _validate_string_field(sc_dict.get("spoken_text_km", ""), "spoken_text_km", idx, allow_empty=True)
            shot_size = _validate_string_field(sc_dict.get("shot_size", "Medium Shot"), "shot_size", idx, allow_empty=False)
            camera = _validate_string_field(sc_dict.get("camera_action", "Static"), "camera_action", idx, allow_empty=False)
            visual = _validate_string_field(sc_dict.get("visual_action", ""), "visual_action", idx, allow_empty=False)
            screen_txt = _validate_string_field(sc_dict.get("on_screen_text_km", ""), "on_screen_text_km", idx, allow_empty=True)
            editing = _validate_string_field(sc_dict.get("editing_note", ""), "editing_note", idx, allow_empty=True)
            audio = _validate_string_field(sc_dict.get("audio_note", ""), "audio_note", idx, allow_empty=True)

            scene = Scene(
                scene_number=sc_num_raw,
                start_seconds=start_s,
                end_seconds=end_s,
                spoken_text_km=spoken,
                shot_size=shot_size,
                camera_action=camera,
                visual_action=visual,
                on_screen_text_km=screen_txt,
                editing_note=editing,
                audio_note=audio,
            )
            scenes.append(scene)

        # 3. Strict Timeline Validation (NO unsafe repositioning)
        validation_notes: List[str] = []

        # Rule A: Scene 1 must start at 0
        if scenes[0].start_seconds != 0:
            raise ValidationError(f"ប្លង់ដំបូងត្រូវតែចាប់ផ្តើមពីវិនាទី 0 (បច្ចុប្បន្នចាប់ផ្តើមពី {scenes[0].start_seconds}s)")

        # Rule B: Chronological, non-zero, consecutive (no gaps, no overlaps)
        for i, sc in enumerate(scenes):
            if sc.end_seconds <= sc.start_seconds:
                raise ValidationError(f"ប្លង់ទី {sc.scene_number}: ពេលវេលាបញ្ចប់ ({sc.end_seconds}s) ត្រូវតែធំជាងពេលវេលាចាប់ផ្តើម ({sc.start_seconds}s)")

            if i > 0:
                prev_end = scenes[i - 1].end_seconds
                if sc.start_seconds != prev_end:
                    if sc.start_seconds > prev_end:
                        raise ValidationError(f"ចន្លោះប្រហោងពេលវេលា (Gap) រវាងប្លង់ {scenes[i-1].scene_number} ({prev_end}s) និងប្លង់ {sc.scene_number} ({sc.start_seconds}s)")
                    else:
                        raise ValidationError(f"ពេលវេលាជាន់គ្នា (Overlap) រវាងប្លង់ {scenes[i-1].scene_number} (ដល់ {prev_end}s) និងប្លង់ {sc.scene_number} (ចាប់ផ្តើមពី {sc.start_seconds}s)")

        # Rule C: Final scene end-time check with narrow documented tolerance (<= 1s only)
        last_end = scenes[-1].end_seconds
        diff = target_duration_seconds - last_end
        if last_end != target_duration_seconds:
            # Narrow tolerance: only if continuous and difference is at most 1 second
            if abs(diff) <= 1 and (target_duration_seconds > scenes[-1].start_seconds):
                scenes[-1].end_seconds = target_duration_seconds
                note = f"បានកែសម្រួល {diff:+d} វិនាទីលើប្លង់ចុងក្រោយ ដើម្បីបញ្ចប់ចំរយៈពេលកំណត់ {target_duration_seconds}s"
                validation_notes.append(note)
                logger.info(note)
            else:
                raise ValidationError(f"ប្លង់ចុងក្រោយបញ្ចប់នៅ {last_end}s មិនត្រូវនឹងរយៈពេលកំណត់ {target_duration_seconds}s ឡើយ (ខុសគ្នា {diff}s)")

        # 4. Recalculate speaking estimates and warnings after final timeline confirmation
        for sc in scenes:
            available_s = sc.end_seconds - sc.start_seconds
            if sc.spoken_text_km and sc.spoken_text_km.strip():
                est_s = estimate_speaking_duration(sc.spoken_text_km, user_pace)
                is_too_long = bool(est_s > available_s)
            else:
                est_s = 0.0
                is_too_long = False

            sc.estimated_spoken_seconds = est_s
            sc.is_dialogue_too_long = is_too_long

        total_speaking_s = round(sum(sc.estimated_spoken_seconds for sc in scenes), 1)

        plan = ScriptPlan(
            title=title,
            target_audience=target_audience,
            hook=hook,
            caption=caption,
            hashtags=hashtags,
            cta=cta,
            target_duration_seconds=target_duration_seconds,
            estimated_speaking_seconds=total_speaking_s,
            scenes=scenes,
            is_timeline_valid=True,
            validation_notes=validation_notes,
            raw_response=raw_json_str,
        )

        formatted_output = format_script_for_telegram(plan, user_pace)
        return PlanResult(
            success=True,
            plan=plan,
            formatted_text=formatted_output,
            error_message=None,
            validation_notes=validation_notes,
        )

    except ValidationError as ve:
        err_msg = str(ve)
        logger.warning(f"Script validation failed: {err_msg}")
        user_err_msg = (
            f"⚠️ *ផែនការថតមិនឆ្លងកាត់ការផ្ទៀងផ្ទាត់ (Validation Failed)*\n\n"
            f"មូលហេតុ៖ _{err_msg}_\n\n"
            f"🔄 _Script ចាស់ដែលជោគជ័យរបស់អ្នកត្រូវបានរក្សាទុកដដែល។ សូមចុច [🔁 បង្កើតម្ដងទៀត] ដើម្បីសាកល្បងឡើងវិញ!_"
        )
        return PlanResult(
            success=False,
            plan=None,
            formatted_text=user_err_msg,
            error_message=err_msg,
        )
    except Exception as e:
        err_msg = f"Unexpected error during validation: {e}"
        logger.error(err_msg, exc_info=True)
        user_err_msg = (
            "⚠️ *កំហុសក្នុងការផ្ទៀងផ្ទាត់ Script*\n\n"
            "ប្រព័ន្ធមិនអាចផ្ទៀងផ្ទាត់ទម្រង់ប្លង់ថតបានឡើយ។ Script ចាស់របស់អ្នកត្រូវបានរក្សាទុកដដែល។\n"
            "👉 សូមចុច [🔁 បង្កើតម្ដងទៀត] ដើម្បីបង្កើតជាថ្មី!"
        )
        return PlanResult(
            success=False,
            plan=None,
            formatted_text=user_err_msg,
            error_message=err_msg,
        )

def format_script_for_telegram(plan: ScriptPlan, user_pace: float = DEFAULT_CHARS_PER_SECOND) -> str:
    """
    Formats the validated ScriptPlan into clean, human-readable Telegram Markdown blocks.
    Never exposes raw JSON or tracebacks to users.
    Discloses that speaking duration is an approximate character-unit heuristic.
    """
    dur_label = f"{plan.target_duration_seconds} វិនាទី" if plan.target_duration_seconds < 60 else f"{plan.target_duration_seconds // 60} នាទី ({plan.target_duration_seconds} វិនាទី)"

    lines = []
    lines.append(f"🎬 *{plan.title}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    if plan.target_audience:
        lines.append(f"👥 *ទស្សនិកជនគោលដៅ*: {plan.target_audience}")
    lines.append(f"⏱️ *រយៈពេលវីដេអូកំណត់*: `{dur_label}`")
    lines.append(
        f"🎙️ *រយៈពេលនិយាយ៖ ប៉ាន់ស្មាន* `~{plan.estimated_speaking_seconds:.1f}s`\n"
        f"ℹ️ _(ការប៉ាន់ស្មានផ្អែកលើចំនួនតួអក្សរភាសាខ្មែរ {user_pace:.1f} តួអក្សរ/s សម្រាប់តែពាក្យនិយាយសុទ្ធ — "
        f"រយៈពេលជាក់ស្តែងអាចប្រែប្រួលតាមការអាន និងការផ្អាក)_"
    )

    if plan.validation_notes:
        for n in plan.validation_notes:
            lines.append(f"ℹ️ _{n}_")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📋 *ផែនការថត និងស្គ្រីបតាមពេលវេលា (Shooting Plan)*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━\n")

    for sc in plan.scenes:
        start_str = format_timestamp(sc.start_seconds)
        end_str = format_timestamp(sc.end_seconds)
        dur = max(0, sc.end_seconds - sc.start_seconds)

        header = f"🎬 *ប្លង់ទី {sc.scene_number} | {start_str}–{end_str}* ({dur}s)"
        lines.append(header)

        if sc.spoken_text_km and sc.spoken_text_km.strip():
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


def parse_and_validate_script_plan(
    raw_json_str: str,
    target_duration_seconds: int,
    user_pace: float = DEFAULT_CHARS_PER_SECOND
) -> Optional[ScriptPlan]:
    """Helper wrapper for backward compatibility. Returns ScriptPlan if valid, None otherwise."""
    result = validate_and_build_plan(raw_json_str, target_duration_seconds, user_pace)
    return result.plan if result.success else None
