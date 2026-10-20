"""
app/services/generation.py - Script Generation Execution Pipeline.

Pipeline:
request → prompt → Gemini → JSON parse → schema validation
→ timeline validation → speech estimate → atomic save → render
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.models import (
    GenerationRequest,
    GenerationResult,
    SavedScript,
    ErrorCodes,
    UserKey,
)
from app.storage import Storage
from app.task_manager import TaskManager
from ai_service import AIService
from script_models import validate_and_build_plan, parse_duration_seconds
from prompts import (
    get_script_generation_prompt,
    get_pov_story_prompt,
    get_myth_reality_prompt,
    get_before_after_prompt,
    get_hot_take_prompt,
    get_top_list_prompt,
    get_comedy_prompt,
)

logger = logging.getLogger(__name__)

VALID_DURATIONS = {60, 120, 180, 300}

async def execute_generation_request(
    request: GenerationRequest,
    storage: Storage,
    ai: AIService,
    token: int,
    task_mgr: TaskManager,
) -> GenerationResult:
    """
    Executes a complete generation request snapshot.
    Validates JSON, schema, and timeline before atomically saving to SQLite.
    Preserves exact failed request for Retry if generation or validation fails.
    """
    draft = request.draft_snapshot
    target_s = draft.get("duration_seconds", 60)
    if target_s not in VALID_DURATIONS:
        target_s = 60

    dur_str = f"{target_s} វិនាទី" if target_s < 60 else f"{target_s // 60} នាទី"
    format_id = draft.get("format_id", "3whs")
    topic = draft.get("topic", "").strip()
    audience = draft.get("audience", topic)

    if not topic:
        err_msg = "⚠️ សូមបញ្ចូលប្រធានបទមាតិកាជាមុនសិន។"
        storage.save_failed_request(request.owner, request, ErrorCodes.INVALID_INPUT, err_msg)
        return GenerationResult(success=False, error_code=ErrorCodes.INVALID_INPUT, user_message_km=err_msg)

    # 1. Build prompt based on format
    if format_id == "comedy" or request.operation == "comedy" or draft.get("comedy_style"):
        style = draft.get("comedy_style", "everyday")
        actors = draft.get("actor_count", 1)
        prompt = get_comedy_prompt(topic, style, actors, dur_str)
    elif format_id == "pov":
        prompt = get_pov_story_prompt(topic, audience, dur_str)
    elif format_id == "myth":
        prompt = get_myth_reality_prompt(topic, audience, dur_str)
    elif format_id == "transform":
        prompt = get_before_after_prompt(topic, audience, dur_str)
    elif format_id == "hottake":
        prompt = get_hot_take_prompt(topic, audience, dur_str)
    elif format_id == "toplist":
        prompt = get_top_list_prompt(topic, audience, dur_str)
    else:
        prompt = get_script_generation_prompt(topic, dur_str)

    # Attach evidence guidance if present
    if request.evidence_snapshot:
        ev_lines = []
        for ev in request.evidence_snapshot:
            ev_lines.append(f"• [{ev.id}] {ev.publisher}: {ev.title} ({ev.url})")
        prompt += f"\n\n[ប្រភពព័ត៌មានយោងពិតប្រាកដដែលបានស្រង់មក]:\n" + "\n".join(ev_lines)

    # 2. Call Gemini
    raw_response = await ai.generate_response(prompt, is_json=True)

    # Check for cancellation before processing result
    if not task_mgr.is_current_request(request.owner, token):
        logger.info(f"Request {request.id} was cancelled before plan validation")
        return GenerationResult(success=False, error_code=ErrorCodes.CANCELLED, user_message_km="សំណើត្រូវបានបោះបង់")

    # 3. Check for API / Quota / Timeout error
    if ai._is_error_response(raw_response):
        err_code = ErrorCodes.QUOTA if "quota" in raw_response.lower() else (
            ErrorCodes.TIMEOUT if "timeout" in raw_response.lower() else ErrorCodes.INTERNAL_ERROR
        )
        storage.save_failed_request(request.owner, request, err_code, raw_response)
        return GenerationResult(success=False, error_code=err_code, user_message_km=raw_response)

    # 4. Strict Plan and Timeline Validation
    plan_result = validate_and_build_plan(raw_response, target_s, request.pace_units_per_second)
    if not plan_result.success or plan_result.plan is None:
        err_msg = plan_result.formatted_text
        err_code = ErrorCodes.INVALID_TIMELINE if "Overlap" in (plan_result.error_message or "") or "Gap" in (plan_result.error_message or "") else ErrorCodes.INVALID_SCHEMA
        storage.save_failed_request(request.owner, request, err_code, err_msg)
        return GenerationResult(success=False, error_code=err_code, user_message_km=err_msg)

    # 5. Coordinated check before atomic save to prevent check-then-save race
    if not task_mgr.is_current_request(request.owner, token):
        logger.info(f"Request {request.id} was cancelled during plan validation; suppressing save")
        return GenerationResult(success=False, error_code=ErrorCodes.CANCELLED, user_message_km="សំណើត្រូវបានបោះបង់")

    # 6. Save successful script atomically
    script_id = request.source_script_id or request.id
    version = (request.source_script_version + 1) if request.source_script_version else 1
    now_utc = datetime.now(timezone.utc)

    saved_script = SavedScript(
        id=script_id,
        version=version,
        owner=request.owner,
        request_snapshot=request,
        plan=plan_result.plan,
        created_at=now_utc,
    )

    storage.save_successful_script(saved_script)
    logger.info(f"Saved successful script {saved_script.id} v{saved_script.version} for {request.owner.key_str}")

    return GenerationResult(
        success=True,
        script=saved_script,
        user_message_km=plan_result.formatted_text,
    )
