"""Offline tests: no model requests, database writes or client processes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_client", ROOT / "scripts/local-client.py")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
spec2 = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install-local-clients.py")
installer = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(installer)


class LocalClientTests(unittest.TestCase):
    def test_passthrough(self):
        selected, check, listing, rest = client.parse_args([
            "--local-model", "iq2_xs", "--local-check", "--resume", "session-id",
        ])
        self.assertEqual(selected, "iq2_xs")
        self.assertTrue(check)
        self.assertEqual(rest, ["--resume", "session-id"])

    def test_invalid_model_and_missing_value(self):
        with self.assertRaises(ValueError):
            client.parse_args(["--local-model"])
        with self.assertRaises(ValueError):
            client.choose("not-real", None, False)

    def test_budget_leaves_server_headroom(self):
        for actual in [32768, 65536, 131072, 262144]:
            limits = client.budget({"max_context": actual})
            self.assertLessEqual(limits["context"], actual - 16384)
            self.assertLess(limits["threshold"] + limits["output"] + 8, actual)
            self.assertGreaterEqual(limits["threshold"], 4096)
        self.assertEqual(client.budget({"max_context": 131072})["threshold"], 65536)
        with self.assertRaises(ValueError):
            client.budget({"max_context": 8192})

    def test_active_model_and_mismatch(self):
        profile = client.PROFILES[1]
        state = {"model": client.model_id(profile), "loaded": True, "max_context": 131072}
        self.assertEqual(client.choose(None, state, False), profile)
        self.assertTrue(client.ensure_server(profile, state))
        self.assertFalse(client.ensure_server(client.PROFILES[2], state))

    def test_clawgod_overlay_keeps_permissions_and_hooks(self):
        profile = client.PROFILES[1]
        state = {"model": client.model_id(profile), "loaded": True, "max_context": 131072}
        original = client.load_json(client.BASE_SETTINGS)
        cfg, env, command = client.client_config("clawgod", profile, state)
        self.assertEqual(cfg["hooks"], original["hooks"])
        self.assertEqual(cfg["permissions"], original["permissions"])
        self.assertEqual(cfg["env"]["CLAUDE_CODE_MAX_CONTEXT_TOKENS"], "98304")
        self.assertEqual(cfg["env"]["CLAUDE_CODE_AUTO_COMPACT_WINDOW"], "81920")
        self.assertEqual(cfg["model"], state["model"])
        self.assertEqual(client.load_json(client.BASE_SETTINGS), original)
        self.assertNotIn("--session-id", command)
        _, _, safe = client.client_config("clawgod-safe", profile, state)
        self.assertNotIn("--dangerously-skip-permissions", safe)

    def test_opencode_overlay_uses_ccswitch_provider(self):
        profile = client.PROFILES[1]
        state = {"model": client.model_id(profile), "loaded": True, "max_context": 131072}
        fake = {"provider": {"strata": installer.PROVIDER}, "model": "remote/keep"}
        with patch.object(client, "load_json", return_value=fake):
            cfg, env, command = client.client_config("opencode", profile, state)
        self.assertEqual(fake["model"], "remote/keep")
        self.assertEqual(cfg["compaction"]["reserved"], 16384)
        self.assertEqual(cfg["tool_output"]["max_bytes"], 12000)
        self.assertEqual(len(cfg["provider"]["strata"]["models"]), 4)
        self.assertEqual(cfg["small_model"], cfg["model"])
        self.assertEqual(command[0], str(client.OPENCODE))
        # Provider remains unchanged: the process-only input budget is a separate copy.
        self.assertEqual(installer.PROVIDER["models"][profile[1]]["limit"]["input"], 73728)

    def test_claude_uses_native_executable_with_same_local_settings(self):
        profile = client.PROFILES[1]
        state = {"model": client.model_id(profile), "loaded": True, "max_context": 131072}
        cfg, env, command = client.client_config("claude", profile, state)
        claw_cfg, _, claw_command = client.client_config("clawgod", profile, state)
        self.assertEqual(command[0], str(client.CLAUDE))
        self.assertNotIn(str(client.BUN), command)
        self.assertFalse(any("cli.cjs" in arg for arg in command))
        self.assertEqual(command[1:-2], claw_command[2:-3])
        self.assertEqual(cfg, claw_cfg)
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "http://127.0.0.1:8080")
        self.assertNotIn("--dangerously-skip-permissions", command)
        self.assertNotIn("--allowedTools", command)
        self.assertEqual(command[-2:], ["--permission-mode", "default"])
        self.assertIn("--dangerously-skip-permissions", claw_command)

    def test_runtime_context_identifies_verified_backend_not_historical_memory(self):
        for profile in client.PROFILES:
            state = {"model": client.model_id(profile), "loaded": True, "max_context": 131072}
            text = client.runtime_context("claude", profile, state)
            self.assertIn("claude.orig.exe", text)
            self.assertIn("Strata (service=strata), NOT LM Studio", text)
            self.assertIn(client.model_id(profile), text)
            self.assertIn("http://127.0.0.1:8080", text)
            self.assertIn("client budget: 98304", text)
        self.assertIn("clawgod CLI", client.runtime_context("clawgod", profile, state))

    def test_claude_version_does_not_require_backend(self):
        with patch.object(client, "health", side_effect=AssertionError("must not probe")), \
                patch.object(client.subprocess, "call", return_value=0) as run:
            self.assertEqual(client.main(["claude", "--version"]), 0)
            run.assert_called_once_with([str(client.CLAUDE), "--version"])

    def test_disabled_provider_is_not_silently_reenabled(self):
        with patch.object(client, "load_json", return_value={"provider": {}}):
            with self.assertRaises(ValueError):
                client.client_config("opencode", client.PROFILES[1], {"max_context": 131072})


if __name__ == "__main__":
    unittest.main()
