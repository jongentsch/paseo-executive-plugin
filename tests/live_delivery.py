"""Opt-in real Paseo worker -> real Hermes pre_llm_call dispatch smoke.

Uses an isolated event store and hook session; does not impersonate an open desktop chat.
"""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from hermes_cli.plugins import PluginContext, PluginManager
from hermes_cli.plugins_manifest import PluginManifest
from paseo_executive.core import Store
from paseo_executive.runtime import Runtime
from paseo_executive.tools import register


def main():
    with tempfile.TemporaryDirectory(prefix="paseo-delivery-") as directory:
        runtime = Runtime(Store(directory))
        runtime.store.set_setting("notification_session_key", "desktop")
        manager = PluginManager(scope_key=directory)
        ctx = PluginContext(PluginManifest(name="paseo-executive", source="user"), manager)
        with patch("paseo_executive.tools.get_runtime", return_value=runtime):
            register(ctx)
            manager.invoke_hook("pre_llm_call", task_id="paseo-delivery-smoke", platform="desktop")
            try:
                worker = runtime.executive.spawn("local", "Reply exactly PASEO_DELIVERY_OK. Do not modify files or run commands.", str(Path.cwd()), "codex", title="Paseo delivery verification")["agent"]["id"]
                print(json.dumps({"worker": worker}), flush=True)
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    events = [e for e in runtime.store.events() if e["agent"] == worker and e["kind"] == "completed" and "PASEO_DELIVERY_OK" in json.dumps(e["result"])]
                    if events:
                        event = events[-1]
                        assert event["delivered"] == 0
                        results = manager.invoke_hook("pre_llm_call", task_id="paseo-delivery-smoke", platform="desktop")
                        assert any("PASEO_DELIVERY_OK" in r.get("context", "") for r in results)
                        event = runtime.store.get_event(event["id"])
                        assert event["delivered"] == 1
                        print(json.dumps({"worker": worker, "event_id": event["id"], "kind": event["kind"], "source": event["context"]["observation"]["source"], "delivered": event["delivered"], "hermes_hook_context": True}), flush=True)
                        return
                    time.sleep(1)
                raise RuntimeError("Completion event timeout")
            finally:
                runtime.stop()
                if "worker" in locals():
                    runtime.executive.cli.call(runtime.store.host("local"), "archive", worker)


if __name__ == "__main__":
    main()
