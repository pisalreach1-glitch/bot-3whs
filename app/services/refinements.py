"""
app/services/refinements.py - Script Refinement Operations: Shorten, Regenerate, and Hook Alternatives.

Shortening and regeneration create new validated versions atomically.
Hooks are stored separately and only applied after user selection with timeline revalidation.
"""

import re
import uuid
import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

from app.models import (
    UserKey,
    SavedScript,
    GenerationRequest,
    GenerationResult,
    ErrorCodes,
)
from app.storage import Storage
from app.task_manager import TaskManager
from ai_service import AIService
from script_models import (
    validate_and_build_plan,
    estimate_speaking_duration,
    DEFAULT_CHARS_PER_SECOND,
)
from prompts import get_refine_shorten_prompt, get_refine_hook_prompt

logger = logging.getLogger(__name__)

async def shorten_script(
    user_key: UserKey,
    script_id: str,
    version: int,
    storage: Storage,
    ai: AIService,
    task_mgr: TaskManager,
    token: int,
) -> GenerationResult:
    """Condenses dialogue while preserving selected video duration. Creates a new version atomically."""
    script = storage.get_script(script_id, version)
    if not script or script.owner != user_key:
        return GenerationResult(success=False, error_code=ErrorCodes.INVALID_INPUT, user_message_km="⚠️ រកមិនឃើញ Script ដើមដើម្បីកាត់បន្ថយឡើយ។")

    plan = script.plan
    target_s = plan.target_duration_seconds
    dur_str = f"{target_s} វិនាទី"

    # Use existing scenes/script text
    lines = [f"Title: {plan.title}"]
    for sc in plan.scenes:
        lines.append(f"Scene {sc.scene_number} ({sc.start_seconds}-{sc.end_seconds}s): {sc.spoken_text_km}")
    script_content = "\n".join(lines)

    req_id = f"req_{uuid.uuid4().hex[:8]}"
    pace = script.request_snapshot.pace_units_per_second
    new_req = GenerationRequest(
        id=req_id,
        operation="shorten",
        owner=user_key,
        draft_snapshot=script.request_snapshot.draft_snapshot,
        pace_units_per_second=pace,
        source_script_id=script_id,
        source_script_version=version,
        evidence_snapshot=script.request_snapshot.evidence_snapshot,
    )

    prompt = get_refine_shorten_prompt(script_content, dur_str)
    raw_response = await ai.generate_response(prompt, is_json=True)

    if not task_mgr.is_current_request(user_key, token):
        return GenerationResult(success=False, error_code=ErrorCodes.CANCELLED, user_message_km="សំណើត្រូវបានបោះបង់", request_id=req_id)

    if ai._is_error_response(raw_response):
        storage.save_failed_request(user_key, new_req, ErrorCodes.QUOTA if "quota" in raw_response.lower() else ErrorCodes.INTERNAL_ERROR, raw_response)
        return GenerationResult(success=False, error_code=ErrorCodes.INTERNAL_ERROR, user_message_km=raw_response, request_id=req_id)

    plan_result = validate_and_build_plan(raw_response, target_s, pace)

    if not plan_result.success or plan_result.plan is None:
        storage.save_failed_request(user_key, new_req, ErrorCodes.INVALID_SCHEMA, plan_result.formatted_text)
        return GenerationResult(success=False, error_code=ErrorCodes.INVALID_SCHEMA, user_message_km=plan_result.formatted_text, request_id=req_id)

    if not task_mgr.is_current_request(user_key, token):
        return GenerationResult(success=False, error_code=ErrorCodes.CANCELLED, user_message_km="សំណើត្រូវបានបោះបង់", request_id=req_id)

    # Create new version atomically
    new_version = version + 1
    new_script = SavedScript(
        id=script_id,
        version=new_version,
        owner=user_key,
        request_snapshot=new_req,
        plan=plan_result.plan,
        created_at=datetime.now(timezone.utc),
    )
    storage.save_successful_script(new_script)
    logger.info(f"Shortened script {script_id} created as version {new_version}")

    return GenerationResult(success=True, script=new_script, user_message_km="✅ Script ត្រូវបានសង្ខេបឱ្យខ្លីខ្លឹមរួចរាល់!", request_id=req_id)

async def regenerate_script(
    user_key: UserKey,
    script_id: str,
    version: int,
    storage: Storage,
    ai: AIService,
    task_mgr: TaskManager,
    token: int,
) -> GenerationResult:
    """Regenerates script using the exact saved request snapshot from previous version."""
    script = storage.get_script(script_id, version)
    if not script or script.owner != user_key:
        return GenerationResult(success=False, error_code=ErrorCodes.INVALID_INPUT, user_message_km="⚠️ រកមិនឃើញ Script ដើមដើម្បីបង្កើតឡើងវិញឡើយ។")

    from app.services.generation import execute_generation_request

    req_snapshot = script.request_snapshot
    new_req = GenerationRequest(
        id=f"req_{uuid.uuid4().hex[:8]}",
        operation="regenerate",
        owner=user_key,
        draft_snapshot=req_snapshot.draft_snapshot,
        pace_units_per_second=req_snapshot.pace_units_per_second,
        source_script_id=script_id,
        source_script_version=version,
        evidence_snapshot=req_snapshot.evidence_snapshot,
    )

    return await execute_generation_request(new_req, storage, ai, token, task_mgr)

async def generate_hook_options(
    user_key: UserKey,
    script_id: str,
    version: int,
    storage: Storage,
    ai: AIService,
) -> Tuple[Optional[str], List[dict], Optional[str]]:
    """Generates 3 hook options and saves them separately, linked to script ID and version."""
    script = storage.get_script(script_id, version)
    if not script or script.owner != user_key:
        return None, [], "⚠️ រកមិនឃើញ Script ដើមឡើយ។"

    plan = script.plan
    summary_text = f"Title: {plan.title}\nOpening: {plan.scenes[0].spoken_text_km if plan.scenes else ''}"
    prompt = get_refine_hook_prompt(summary_text)

    raw_response = await ai.generate_response(prompt, is_json=False)
    if ai._is_error_response(raw_response):
        return None, [], raw_response

    # Parse 3 options
    hooks: List[dict] = []
    blocks = re.split(r"(?=✨\s*\*\*ជម្រើសទី|⚠️\s*\*\*ជម្រើសទី|🎯\s*\*\*ជម្រើសទី)", raw_response)
    valid_blocks = [b.strip() for b in blocks if "ជម្រើសទី" in b]

    types = ["Curiosity Hook", "Warning Hook", "Direct Value Hook"]
    for idx, block in enumerate(valid_blocks[:3]):
        h_type = types[idx] if idx < len(types) else f"Hook {idx+1}"
        speech_match = re.search(r"🗣️\s*\*\*ពាក្យនិយាយ\*\*[៖:\s]+\"([^\"]+)\"", block)
        if not speech_match:
            speech_match = re.search(r"🗣️\s*\*\*ពាក្យនិយាយ\*\*[៖:\s]+([^\n]+)", block)
        visual_match = re.search(r"🎥\s*\*\*កាយវិការ[^\*]*\*\*[៖:\s]+([^\n]+)", block)

        spoken = speech_match.group(1).strip() if speech_match else f"ជម្រើស Hook ទី {idx+1}"
        visual = visual_match.group(1).strip() if visual_match else ""

        hooks.append({
            "type": h_type,
            "spoken_text": spoken,
            "visual": visual,
        })

    if not hooks:
        # Fallback parsing
        hooks = [
            {"type": "Curiosity Hook", "spoken_text": "តើអ្នកដឹងទេថា កំហុសមួយនេះធ្វើឱ្យមនុស្សភាគច្រើនខាតបង់?", "visual": "ចង្អុលកាមេរ៉ា"},
            {"type": "Warning Hook", "spoken_text": "ឈប់ធ្វើបែបនេះភ្លាម ប្រសិនបើអ្នកមិនចង់ស្តាយក្រោយ!", "visual": "កាយវិការហាម"},
            {"type": "Direct Value Hook", "spoken_text": "នេះជាវិធីងាយៗ ៣ យ៉ាងជួយដោះស្រាយបញ្ហារបស់អ្នកភ្លាមៗ!", "visual": "ទឹកមុខជឿជាក់"},
        ]

    token = f"h_{uuid.uuid4().hex[:8]}"
    storage.save_hook_options(token, script_id, version, hooks)
    return token, hooks, None

def apply_hook_option(
    user_key: UserKey,
    script_id: str,
    version: int,
    option_index: int,
    options_token: str,
    storage: Storage,
) -> GenerationResult:
    """Applies selected hook to Scene 1, re-validates timeline and speech estimate, creates new version."""
    opts_data = storage.get_hook_options(options_token)
    if not opts_data or opts_data["script_id"] != script_id or opts_data["script_version"] != version:
        return GenerationResult(success=False, error_code=ErrorCodes.INVALID_INPUT, user_message_km="⚠️ ជម្រើស Hook នេះផុតកំណត់ ឬមិនត្រឹមត្រូវឡើយ។")

    script = storage.get_script(script_id, version)
    if not script or script.owner != user_key:
        return GenerationResult(success=False, error_code=ErrorCodes.INVALID_INPUT, user_message_km="⚠️ រកមិនឃើញ Script ដើមឡើយ។")

    options = opts_data["options"]
    if option_index < 1 or option_index > len(options):
        return GenerationResult(success=False, error_code=ErrorCodes.INVALID_INPUT, user_message_km="⚠️ លេខជម្រើស Hook មិនត្រឹមត្រូវ។")

    chosen_hook = options[option_index - 1]
    new_plan = deepcopy(script.plan)

    if not new_plan.scenes:
        return GenerationResult(success=False, error_code=ErrorCodes.INVALID_SCHEMA, user_message_km="⚠️ Script គ្មានប្លង់ថតឡើយ។")

    # Update Scene 1
    sc1 = new_plan.scenes[0]
    sc1.spoken_text_km = chosen_hook["spoken_text"]
    if chosen_hook.get("visual"):
        sc1.visual_action = chosen_hook["visual"]

    # Re-estimate speaking duration
    pace = script.request_snapshot.pace_units_per_second
    est_s = estimate_speaking_duration(sc1.spoken_text_km, pace)
    avail_s = sc1.end_seconds - sc1.start_seconds
    sc1.estimated_spoken_seconds = est_s
    sc1.is_dialogue_too_long = bool(est_s > avail_s)

    # If dialogue is excessively long (> 1.8x available scene time), preserve original!
    if est_s > (avail_s * 1.8):
        return GenerationResult(
            success=False,
            error_code=ErrorCodes.INVALID_TIMELINE,
            user_message_km=f"⚠️ Hook នេះវែងពេក (~{est_s:.1f}s លើសប្រវែងប្លង់ទី ១ ដែលមានត្រឹម {avail_s}s)។ Script ដើមត្រូវបានរក្សាទុកដដែល។"
        )

    # Recalculate total estimated speech
    new_plan.estimated_speaking_seconds = round(sum(s.estimated_spoken_seconds for s in new_plan.scenes), 1)

    new_version = version + 1
    new_req = GenerationRequest(
        id=f"req_{uuid.uuid4().hex[:8]}",
        operation="apply_hook",
        owner=user_key,
        draft_snapshot=script.request_snapshot.draft_snapshot,
        pace_units_per_second=pace,
        source_script_id=script_id,
        source_script_version=version,
        selected_hook=chosen_hook,
        evidence_snapshot=script.request_snapshot.evidence_snapshot,
    )

    new_script = SavedScript(
        id=script_id,
        version=new_version,
        owner=user_key,
        request_snapshot=new_req,
        plan=new_plan,
        created_at=datetime.now(timezone.utc),
    )
    storage.save_successful_script(new_script)
    logger.info(f"Applied Hook option {option_index} to script {script_id} v{new_version}")

    return GenerationResult(success=True, script=new_script, user_message_km="✅ បានប្តូរ Hook ថ្មីជោគជ័យ!")
