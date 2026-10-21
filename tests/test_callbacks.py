"""
tests/test_callbacks.py - Tests for compact callback encoding, decoding, 64-byte limit, and security.
"""

import unittest
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
    decode_callback,
    check_callback_byte_length,
    TELEGRAM_CALLBACK_BYTE_LIMIT,
    CallbackError,
)

class TestCallbacks(unittest.TestCase):
    def test_all_encoded_callbacks_within_64_bytes(self):
        """Telegram strictly enforces a 64-byte UTF-8 limit on callback_data."""
        samples = [
            encode_menu("create"),
            encode_menu("comedy"),
            encode_menu("ideas"),
            encode_menu("last"),
            encode_menu("settings"),
            encode_menu("help"),
            encode_format("misconception", "tok12345678", 42),
            encode_duration("tok12345678", 42, 180),
            encode_generate("tok12345678", 42),
            encode_idea_pick("tok12345678", 2),
            encode_script_action("tok12345678", 1, "shots"),
            encode_script_action("tok12345678", 1, "shorten"),
            encode_hook_pick("tok12345678", 0),
            encode_retry("tok12345678"),
            encode_cancel("tok12345678"),
            encode_setting("dur:120"),
            encode_setting("pace"),
            encode_setting("sub:on"),
            encode_comedy_style("tok12345678", 1, "everyday"),
            encode_comedy_actors("tok12345678", 1, 2),
            encode_nav("back"),
            encode_nav("home"),
        ]
        for data in samples:
            encoded_bytes = len(data.encode("utf-8"))
            self.assertLessEqual(
                encoded_bytes,
                TELEGRAM_CALLBACK_BYTE_LIMIT,
                f"Callback '{data}' exceeded 64 bytes: {encoded_bytes} bytes",
            )

    def test_menu_action_roundtrip(self):
        data = encode_menu("create")
        self.assertEqual(data, "m:create")
        cb = decode_callback(data)
        self.assertEqual(cb.prefix, "m")
        self.assertEqual(cb.action, "create")

    def test_format_pick_roundtrip(self):
        data = encode_format("3whs", "draft_abc", 3)
        self.assertEqual(data, "f:3whs:draft_abc:3")
        cb = decode_callback(data)
        self.assertEqual(cb.prefix, "f")
        self.assertEqual(cb.action, "3whs")
        self.assertEqual(cb.token, "draft_abc")
        self.assertEqual(cb.version_or_rev, 3)

    def test_draft_duration_roundtrip(self):
        data = encode_duration("draft_abc", 2, 120)
        self.assertEqual(data, "d:draft_abc:2:120")
        cb = decode_callback(data)
        self.assertEqual(cb.prefix, "d")
        self.assertEqual(cb.token, "draft_abc")
        self.assertEqual(cb.version_or_rev, 2)
        self.assertEqual(cb.extra, "120")

    def test_generate_roundtrip(self):
        data = encode_generate("draft_abc", 5)
        self.assertEqual(data, "g:draft_abc:5")
        cb = decode_callback(data)
        self.assertEqual(cb.prefix, "g")
        self.assertEqual(cb.token, "draft_abc")
        self.assertEqual(cb.version_or_rev, 5)

    def test_script_action_roundtrip(self):
        for act in ["full", "read", "shots", "caption", "hooks", "shorten", "regen"]:
            data = encode_script_action("scr_123", 2, act)
            self.assertEqual(data, f"s:scr_123:2:{act}")
            cb = decode_callback(data)
            self.assertEqual(cb.prefix, "s")
            self.assertEqual(cb.token, "scr_123")
            self.assertEqual(cb.version_or_rev, 2)
            self.assertEqual(cb.action, act)

    def test_hook_pick_roundtrip(self):
        data = encode_hook_pick("opt_tok", 1)
        self.assertEqual(data, "h:opt_tok:1")
        cb = decode_callback(data)
        self.assertEqual(cb.prefix, "h")
        self.assertEqual(cb.token, "opt_tok")
        self.assertEqual(cb.extra, "1")

    def test_retry_and_cancel_roundtrip(self):
        r_data = encode_retry("req_123")
        self.assertEqual(r_data, "r:req_123")
        cb_r = decode_callback(r_data)
        self.assertEqual(cb_r.prefix, "r")
        self.assertEqual(cb_r.token, "req_123")

        x_data = encode_cancel("req_456")
        self.assertEqual(x_data, "x:req_456")
        cb_x = decode_callback(x_data)
        self.assertEqual(cb_x.prefix, "x")
        self.assertEqual(cb_x.token, "req_456")

    def test_malformed_callbacks_fail_safely(self):
        with self.assertRaises(CallbackError):
            decode_callback("")
        with self.assertRaises(CallbackError):
            decode_callback("unknown:action")
        with self.assertRaises(CallbackError):
            decode_callback("f:invalid")
        with self.assertRaises(CallbackError):
            decode_callback("d:only_one")
        with self.assertRaises(CallbackError):
            decode_callback("g:no_rev")
        with self.assertRaises(CallbackError):
            decode_callback("s:short")

    def test_oversized_callback_raises(self):
        oversized = "m:" + ("a" * 70)
        with self.assertRaises(CallbackError):
            check_callback_byte_length(oversized)

    def test_no_raw_json_or_urls_in_callbacks(self):
        """Callbacks must never contain URLs or JSON payloads."""
        callbacks = [
            encode_format("3whs", "draft1", 1),
            encode_generate("draft1", 1),
            encode_script_action("script1", 1, "shots"),
            encode_idea_pick("batch1", 1),
        ]
        for cb in callbacks:
            self.assertNotIn("http://", cb)
            self.assertNotIn("https://", cb)
            self.assertNotIn("{", cb)
            self.assertNotIn("}", cb)

if __name__ == "__main__":
    unittest.main()
