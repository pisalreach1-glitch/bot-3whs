"""
app/models.py - Core domain and state models for 3WHs Bot.

Enforces typed UserKey (chat_id, user_id), Drafts, GenerationRequests,
SavedScripts, EvidenceRecords, and NavigationState.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from script_models import ScriptPlan, Scene

# Standard Error Codes
class ErrorCodes:
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_JSON = "INVALID_JSON"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    INVALID_TIMELINE = "INVALID_TIMELINE"
    QUOTA = "QUOTA"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"

@dataclass(frozen=True)
class UserKey:
    """Combines chat_id and user_id to isolate personal state across group chats."""
    chat_id: int
    user_id: int

    def __post_init__(self):
        try:
            cid = int(self.chat_id)
        except Exception:
            cid = 0
        try:
            uid = int(self.user_id)
        except Exception:
            uid = cid
        object.__setattr__(self, "chat_id", cid)
        object.__setattr__(self, "user_id", uid)

    @property
    def key_str(self) -> str:
        return f"{self.chat_id}:{self.user_id}"

    @classmethod
    def from_str(cls, s: str) -> "UserKey":
        parts = s.split(":")
        return cls(chat_id=int(parts[0]), user_id=int(parts[1]))

@dataclass
class EvidenceRecord:
    id: str
    url: str
    platform_or_feed: str
    publisher: str
    retrieved_at: datetime
    title: str
    published_at: Optional[datetime] = None
    observed_format: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "platform_or_feed": self.platform_or_feed,
            "publisher": self.publisher,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
            "title": self.title,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "observed_format": self.observed_format,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvidenceRecord":
        retrieved_dt = datetime.fromisoformat(d["retrieved_at"]) if d.get("retrieved_at") else datetime.now(timezone.utc)
        published_dt = datetime.fromisoformat(d["published_at"]) if d.get("published_at") else None
        return cls(
            id=str(d.get("id", "")),
            url=str(d.get("url", "")),
            platform_or_feed=str(d.get("platform_or_feed", "rss")),
            publisher=str(d.get("publisher", "")),
            retrieved_at=retrieved_dt,
            title=str(d.get("title", "")),
            published_at=published_dt,
            observed_format=d.get("observed_format"),
            metrics=d.get("metrics"),
        )

@dataclass
class Draft:
    id: str
    revision: int
    format_id: str
    topic: str
    duration_seconds: int
    audience: str
    comedy_style: Optional[str] = None
    actor_count: Optional[int] = None
    evidence_ids: List[str] = field(default_factory=list)
    current_step: str = "format"
    owner: Optional[UserKey] = None
    niche: Optional[str] = None

    def to_snapshot(self) -> dict:
        return self.to_dict()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "revision": self.revision,
            "format_id": self.format_id,
            "topic": self.topic,
            "duration_seconds": self.duration_seconds,
            "audience": self.audience,
            "comedy_style": self.comedy_style,
            "actor_count": self.actor_count,
            "evidence_ids": list(self.evidence_ids),
            "current_step": self.current_step,
            "owner": self.owner.key_str if self.owner else None,
            "niche": self.niche,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Draft":
        owner_val = d.get("owner")
        owner = UserKey.from_str(owner_val) if isinstance(owner_val, str) else None
        return cls(
            id=str(d["id"]),
            revision=int(d.get("revision", 1)),
            format_id=str(d.get("format_id", "3whs")),
            topic=str(d.get("topic", "")),
            duration_seconds=int(d.get("duration_seconds", 60)),
            audience=str(d.get("audience", "")),
            comedy_style=d.get("comedy_style"),
            actor_count=int(d["actor_count"]) if d.get("actor_count") is not None else None,
            evidence_ids=list(d.get("evidence_ids", [])),
            current_step=str(d.get("current_step", "format")),
            owner=owner,
            niche=d.get("niche"),
        )

@dataclass
class GenerationRequest:
    id: str
    operation: str  # "create" | "regenerate" | "shorten" | "apply_hook"
    owner: UserKey
    draft_snapshot: Dict[str, Any]
    pace_units_per_second: float
    source_script_id: Optional[str] = None
    source_script_version: Optional[int] = None
    selected_hook: Optional[Dict[str, Any]] = None
    evidence_snapshot: List[EvidenceRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "operation": self.operation,
            "owner": self.owner.key_str,
            "draft_snapshot": self.draft_snapshot,
            "pace_units_per_second": self.pace_units_per_second,
            "source_script_id": self.source_script_id,
            "source_script_version": self.source_script_version,
            "selected_hook": self.selected_hook,
            "evidence_snapshot": [ev.to_dict() for ev in self.evidence_snapshot],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GenerationRequest":
        evs = [EvidenceRecord.from_dict(ev) for ev in d.get("evidence_snapshot", [])]
        owner = UserKey.from_str(d["owner"]) if isinstance(d["owner"], str) else UserKey(d["owner"][0], d["owner"][1])
        return cls(
            id=str(d["id"]),
            operation=str(d.get("operation", "create")),
            owner=owner,
            draft_snapshot=dict(d.get("draft_snapshot", {})),
            pace_units_per_second=float(d.get("pace_units_per_second", 10.0)),
            source_script_id=d.get("source_script_id"),
            source_script_version=int(d["source_script_version"]) if d.get("source_script_version") is not None else None,
            selected_hook=d.get("selected_hook"),
            evidence_snapshot=evs,
        )

@dataclass
class SavedScript:
    id: str
    version: int
    owner: UserKey
    request_snapshot: GenerationRequest
    plan: ScriptPlan
    created_at: datetime

    def to_dict(self) -> dict:
        # Serialize plan
        plan_dict = {
            "title": self.plan.title,
            "target_audience": self.plan.target_audience,
            "hook": self.plan.hook,
            "caption": self.plan.caption,
            "hashtags": self.plan.hashtags,
            "cta": self.plan.cta,
            "target_duration_seconds": self.plan.target_duration_seconds,
            "estimated_speaking_seconds": self.plan.estimated_speaking_seconds,
            "is_timeline_valid": self.plan.is_timeline_valid,
            "validation_notes": self.plan.validation_notes,
            "raw_response": self.plan.raw_response,
            "scenes": [
                {
                    "scene_number": sc.scene_number,
                    "start_seconds": sc.start_seconds,
                    "end_seconds": sc.end_seconds,
                    "spoken_text_km": sc.spoken_text_km,
                    "shot_size": sc.shot_size,
                    "camera_action": sc.camera_action,
                    "visual_action": sc.visual_action,
                    "on_screen_text_km": sc.on_screen_text_km,
                    "editing_note": sc.editing_note,
                    "audio_note": sc.audio_note,
                    "estimated_spoken_seconds": sc.estimated_spoken_seconds,
                    "is_dialogue_too_long": sc.is_dialogue_too_long,
                }
                for sc in self.plan.scenes
            ],
        }
        return {
            "id": self.id,
            "version": self.version,
            "owner": self.owner.key_str,
            "request_snapshot": self.request_snapshot.to_dict(),
            "plan": plan_dict,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SavedScript":
        p = d["plan"]
        scenes = [
            Scene(
                scene_number=sc["scene_number"],
                start_seconds=sc["start_seconds"],
                end_seconds=sc["end_seconds"],
                spoken_text_km=sc.get("spoken_text_km", ""),
                shot_size=sc.get("shot_size", "Medium Shot"),
                camera_action=sc.get("camera_action", "Static"),
                visual_action=sc.get("visual_action", ""),
                on_screen_text_km=sc.get("on_screen_text_km", ""),
                editing_note=sc.get("editing_note", ""),
                audio_note=sc.get("audio_note", ""),
                estimated_spoken_seconds=float(sc.get("estimated_spoken_seconds", 0.0)),
                is_dialogue_too_long=bool(sc.get("is_dialogue_too_long", False)),
            )
            for sc in p.get("scenes", [])
        ]
        plan = ScriptPlan(
            title=p.get("title", ""),
            target_audience=p.get("target_audience", ""),
            hook=p.get("hook", ""),
            caption=p.get("caption", ""),
            hashtags=p.get("hashtags", []),
            cta=p.get("cta", ""),
            target_duration_seconds=int(p.get("target_duration_seconds", 60)),
            estimated_speaking_seconds=float(p.get("estimated_speaking_seconds", 0.0)),
            scenes=scenes,
            is_timeline_valid=bool(p.get("is_timeline_valid", True)),
            validation_notes=list(p.get("validation_notes", [])),
            raw_response=p.get("raw_response", ""),
        )
        owner = UserKey.from_str(d["owner"]) if isinstance(d["owner"], str) else UserKey(d["owner"][0], d["owner"][1])
        req = GenerationRequest.from_dict(d["request_snapshot"])
        created_at = datetime.fromisoformat(d["created_at"]) if d.get("created_at") else datetime.now(timezone.utc)
        return cls(
            id=str(d["id"]),
            version=int(d["version"]),
            owner=owner,
            request_snapshot=req,
            plan=plan,
            created_at=created_at,
        )

@dataclass
class GenerationResult:
    success: bool
    script: Optional[SavedScript] = None
    error_code: Optional[str] = None
    user_message_km: str = ""
    request_id: Optional[str] = None

@dataclass
class Idea:
    id: int
    topic: str
    hook: str
    suggested_format: str
    source_ids: List[int]
    evidence_status: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "hook": self.hook,
            "suggested_format": self.suggested_format,
            "source_ids": list(self.source_ids),
            "evidence_status": self.evidence_status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Idea":
        return cls(
            id=int(d["id"]),
            topic=str(d.get("topic", "")),
            hook=str(d.get("hook", "")),
            suggested_format=str(d.get("suggested_format", "3whs")),
            source_ids=[int(x) for x in d.get("source_ids", [])],
            evidence_status=str(d.get("evidence_status", "")),
        )

@dataclass
class NavigationState:
    current_screen: str
    screen_history: List[str] = field(default_factory=list)
    draft_id: Optional[str] = None
    selected_script_id: Optional[str] = None
    selected_script_version: Optional[int] = None
