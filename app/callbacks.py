"""
app/callbacks.py - Compact callback encoding and strict decoding under Telegram's 64-byte limit.

Supported schemes:
- m:<menu_action>              (e.g., m:create, m:comedy, m:ideas, m:last, m:settings, m:help, m:retry)
- f:<format_id>:<token>:<rev>  (e.g., f:3whs:d12345:1)
- d:<token>:<rev>:<seconds>    (e.g., d:d12345:1:60)
- g:<token>:<rev>              (e.g., g:d12345:1 - generate)
- i:<batch_token>:<idea_idx>   (e.g., i:b12345:1)
- s:<script_id>:<ver>:<action> (e.g., s:s12345:1:read)
- h:<options_token>:<opt_idx>  (e.g., h:h12345:0)
- r:<request_id>               (e.g., r:r12345 - retry)
- c:sty:<token>:<rev>:<style>  (e.g., c:sty:d12345:1:everyday)
- c:act:<token>:<rev>:<count>  (e.g., c:act:d12345:1:1)
- set:<action>                 (e.g., set:dur:60, set:pace, set:sub:on, set:status)
- n:back, n:home
- x:<request_id>               (cancel)
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

TELEGRAM_CALLBACK_BYTE_LIMIT = 64

class CallbackError(Exception):
    """Raised when callback data is malformed, oversized, or invalid."""
    pass

def check_callback_byte_length(data: str) -> str:
    """Ensures callback data does not exceed Telegram's 64 UTF-8 bytes limit."""
    b = data.encode("utf-8")
    if len(b) > TELEGRAM_CALLBACK_BYTE_LIMIT:
        raise CallbackError(f"Callback data exceeds 64 bytes limit ({len(b)} bytes): {data}")
    return data

# Encoders
def encode_menu(action: str) -> str:
    return check_callback_byte_length(f"m:{action}")

def encode_format(format_id: str, draft_token: str, revision: int) -> str:
    return check_callback_byte_length(f"f:{format_id}:{draft_token}:{revision}")

def encode_duration(draft_token: str, revision: int, seconds: int) -> str:
    return check_callback_byte_length(f"d:{draft_token}:{revision}:{seconds}")

def encode_generate(draft_token: str, revision: int) -> str:
    return check_callback_byte_length(f"g:{draft_token}:{revision}")

def encode_idea_pick(batch_token: str, idea_index: int) -> str:
    return check_callback_byte_length(f"i:{batch_token}:{idea_index}")

def encode_script_action(script_token: str, version: int, action: str) -> str:
    return check_callback_byte_length(f"s:{script_token}:{version}:{action}")

def encode_hook_pick(options_token: str, option_index: int) -> str:
    return check_callback_byte_length(f"h:{options_token}:{option_index}")

def encode_retry(request_token: str) -> str:
    return check_callback_byte_length(f"r:{request_token}")

def encode_cancel(request_token: str) -> str:
    return check_callback_byte_length(f"x:{request_token}")

def encode_nav(action: str) -> str:
    return check_callback_byte_length(f"n:{action}")

def encode_setting(action: str) -> str:
    return check_callback_byte_length(f"set:{action}")

def encode_comedy_style(draft_token: str, revision: int, style: str) -> str:
    return check_callback_byte_length(f"c:sty:{draft_token}:{revision}:{style}")

def encode_comedy_actors(draft_token: str, revision: int, actors: int) -> str:
    return check_callback_byte_length(f"c:act:{draft_token}:{revision}:{actors}")

# Decoders
@dataclass
class DecodedCallback:
    prefix: str
    action: str
    token: Optional[str] = None
    version_or_rev: Optional[int] = None
    extra: Optional[str] = None
    raw_data: str = ""

def decode_callback(data: str) -> DecodedCallback:
    """Strictly decodes callback data into DecodedCallback."""
    if not data or not isinstance(data, str):
        raise CallbackError("Empty or invalid callback data")

    b_len = len(data.encode("utf-8"))
    if b_len > TELEGRAM_CALLBACK_BYTE_LIMIT:
        raise CallbackError(f"Callback data exceeds 64 bytes limit ({b_len} bytes)")

    parts = data.split(":")
    prefix = parts[0]

    if prefix == "m" and len(parts) >= 2:
        return DecodedCallback(prefix="m", action=parts[1], raw_data=data)

    elif prefix == "n" and len(parts) >= 2:
        return DecodedCallback(prefix="n", action=parts[1], raw_data=data)

    elif prefix == "f" and len(parts) >= 4:
        # f:<format_id>:<draft_token>:<revision>
        return DecodedCallback(
            prefix="f",
            action=parts[1],
            token=parts[2],
            version_or_rev=int(parts[3]),
            raw_data=data
        )

    elif prefix == "d" and len(parts) >= 4:
        # d:<draft_token>:<revision>:<seconds>
        return DecodedCallback(
            prefix="d",
            action="set_duration",
            token=parts[1],
            version_or_rev=int(parts[2]),
            extra=parts[3],
            raw_data=data
        )

    elif prefix == "g" and len(parts) >= 3:
        # g:<draft_token>:<revision>
        return DecodedCallback(
            prefix="g",
            action="generate",
            token=parts[1],
            version_or_rev=int(parts[2]),
            raw_data=data
        )

    elif prefix == "i" and len(parts) >= 3:
        # i:<batch_token>:<idea_index>
        return DecodedCallback(
            prefix="i",
            action="pick_idea",
            token=parts[1],
            extra=parts[2],
            raw_data=data
        )

    elif prefix == "s" and len(parts) >= 4:
        # s:<script_token>:<version>:<action>
        return DecodedCallback(
            prefix="s",
            action=parts[3],
            token=parts[1],
            version_or_rev=int(parts[2]),
            raw_data=data
        )

    elif prefix == "h" and len(parts) >= 3:
        # h:<options_token>:<option_index>
        return DecodedCallback(
            prefix="h",
            action="pick_hook",
            token=parts[1],
            extra=parts[2],
            raw_data=data
        )

    elif prefix == "r" and len(parts) >= 2:
        # r:<request_token>
        return DecodedCallback(prefix="r", action="retry", token=parts[1], raw_data=data)

    elif prefix == "x" and len(parts) >= 2:
        # x:<request_token>
        return DecodedCallback(prefix="x", action="cancel", token=parts[1], raw_data=data)

    elif prefix == "set" and len(parts) >= 2:
        # set:<action> or set:dur:<sec>
        sub_action = parts[1]
        extra_val = parts[2] if len(parts) >= 3 else None
        return DecodedCallback(prefix="set", action=sub_action, extra=extra_val, raw_data=data)

    elif prefix == "c" and len(parts) >= 5:
        # c:sty:<draft_token>:<rev>:<style> or c:act:<draft_token>:<rev>:<count>
        c_type = parts[1]
        return DecodedCallback(
            prefix="c",
            action=c_type,
            token=parts[2],
            version_or_rev=int(parts[3]),
            extra=parts[4],
            raw_data=data
        )

    raise CallbackError(f"Unsupported callback format: {data}")
