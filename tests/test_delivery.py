import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from paseo_executive.core import Store
from paseo_executive.runtime import Runtime
from paseo_executive.tools import register

class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.store.set_setting("notification_session_key", "desktop")
        self.runtime = Runtime(self.store)
        self.store.set_setting("desktop_session_key", "desktop-conversation")
        self.event = self.store.event("local", "worker", "completed", {"status": "idle"})
        self.event_bridge = types.ModuleType("hermes_cli.plugin_events")
        self.event_bridge.broadcast_plugin_event = Mock()
        bridge_patch = patch.dict(sys.modules, {"hermes_cli.plugin_events": self.event_bridge})
        bridge_patch.start()
        self.addCleanup(bridge_patch.stop)

    def test_registered_hook_delivers_once_to_destination(self):
        ctx = Mock()
        hooks = {}
        ctx.register_hook.side_effect = lambda name, callback: hooks.update({name: callback})
        with patch("paseo_executive.tools.bind_context", return_value=lambda: None), patch("paseo_executive.tools.get_runtime", return_value=self.runtime), patch.object(self.runtime, "start"):
            register(ctx)
            hook = hooks["pre_llm_call"]
            self.assertIsNone(hook(task_id="other", platform="telegram"))
            result = hook(task_id="desktop-conversation", platform="desktop")
            self.assertIn("completed", result["context"])
            self.assertEqual(self.store.get_event(self.event)["delivered"], 1)
            self.assertIsNone(hook(task_id="desktop-conversation", platform="desktop"))

    def test_rejected_proactive_delivery_can_be_consumed_by_hook(self):
        self.runtime.context = Mock()
        self.runtime.context.inject_message.return_value = False
        self.runtime.deliver()
        self.assertEqual(self.store.get_event(self.event)["delivered"], 0)
        self.assertIsNotNone(self.runtime.hook_context(task_id="desktop-conversation", platform="desktop"))
        self.assertEqual(self.store.get_event(self.event)["delivered"], 1)

    def test_claim_prevents_duplicate_hook_delivery(self):
        self.assertTrue(self.store.claim_event(self.event))
        self.assertIsNone(self.runtime.hook_context(task_id="desktop-conversation", platform="desktop"))

    def test_broadcast_failure_does_not_block_injection(self):
        self.runtime.context = Mock()
        self.runtime.context.inject_message.return_value = True
        self.event_bridge.broadcast_plugin_event.side_effect = RuntimeError("bus unavailable")
        with self.assertLogs("paseo-executive", level="ERROR"):
            self.runtime.deliver()
        self.assertEqual(self.store.get_event(self.event)["delivered"], 1)
        self.assertEqual(self.runtime.context.inject_message.call_args.kwargs["session_key"], "desktop-conversation")

    def test_desktop_alias_waits_for_a_real_conversation(self):
        self.store.set_setting("desktop_session_key", None)
        self.runtime.context = Mock()
        self.runtime.deliver()
        self.runtime.context.inject_message.assert_not_called()
        self.assertEqual(self.store.get_event(self.event)["delivered"], 0)
        result = self.runtime.hook_context(task_id="real-desktop-id", platform="desktop")
        self.assertIn("completed", result["context"])
        self.assertEqual(self.runtime.notification_route(), "real-desktop-id")

    def test_other_desktop_conversation_cannot_take_subscription(self):
        self.assertIsNone(self.runtime.hook_context(task_id="other-desktop-id", platform="desktop"))
        self.assertEqual(self.runtime.notification_route(), "desktop-conversation")
        self.assertEqual(self.store.get_event(self.event)["delivered"], 0)

    def test_formatting_failure_releases_claim_and_retains_event(self):
        with patch("paseo_executive.runtime.event_message", side_effect=ValueError("invalid event")):
            with self.assertRaises(ValueError):
                self.runtime.hook_context(task_id="desktop-conversation")
        event = self.store.get_event(self.event)
        self.assertEqual(event["delivered"], 0)
        self.assertEqual(event["claimed_until"], 0)
