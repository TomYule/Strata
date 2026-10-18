"""Offline regression tests for the ordinary OpenCode safeguards."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("fix_context", Path(__file__).with_name("fix-opencode-context.py"))
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)


class ContextFixTests(unittest.TestCase):
    def test_preserves_remote_configuration(self):
        original = {
            "provider": {"remote": {"options": {"apiKey": "test-only", "baseURL": "https://example.invalid"}}},
            "model": "remote/model", "small_model": "remote/small", "plugin": ["example"],
            "permission": {"bash": "ask"}, "instructions": ["existing.md"],
            "agent": {"build": {"temperature": 0.2}, "compaction": {"model": "remote/small"}},
        }
        result = fix.apply(original)
        for key in ["provider", "model", "small_model", "plugin", "permission"]:
            self.assertEqual(result[key], original[key])
        self.assertEqual(original["instructions"], ["existing.md"])
        self.assertEqual(result["agent"]["compaction"]["model"], "remote/small")
        self.assertEqual(result["agent"]["build"], original["agent"]["build"])

    def test_limits_and_idempotence(self):
        result = fix.apply({})
        self.assertEqual(result["tool_output"], {"max_lines": 200, "max_bytes": 12000})
        self.assertTrue(result["compaction"]["prune"])
        self.assertEqual(result["compaction"]["preserve_recent_tokens"], 8192)
        self.assertNotIn("reserved", result["compaction"])
        self.assertEqual(fix.apply(result), result)


if __name__ == "__main__":
    unittest.main()
