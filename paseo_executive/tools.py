from __future__ import annotations

import json
from .core import ExecutiveError, event_message, required
from .runtime import bind_context, get_runtime
from .skills import register_skills

S = {"type": "string"}


def definition(name, description, properties, required_fields=()):
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": list(required_fields), "additionalProperties": False}}


TOOLS = [
    definition("paseo_hosts", "Manage Paseo daemon hosts. Remote target examples: devbox:6767 or ssh://user@devbox. Local hosts use home. Removing a host leaves its workers running.",
               {"action": {"enum": ["list", "add", "update", "remove", "probe"], "type": "string"},
                "host_id": S, "label": S, "target": S, "home": S, "stream_url": S, "password_env": S, "enabled": {"type": "boolean"}}, ["action"]),
    definition("paseo_spawn", "Delegate a coding task asynchronously to a Paseo worker. Return its ID immediately. cwd is on the selected host. No bypass permission mode is set.",
               {"host_id": S, "prompt": S, "cwd": S, "provider": S, "title": S}, ["host_id", "prompt", "cwd"]),
    definition("paseo_agents", "List, inspect, send a follow-up task, or interrupt a worker on a specific Paseo host.",
               {"action": {"type": "string", "enum": ["list", "inspect", "send", "stop"]}, "host_id": S,
                "agent_id": S, "prompt": S}, ["action", "host_id"]),
    definition("paseo_worker_details", "Read fresh worker state and bounded recent activity or assistant response. Includes assignment context and unverified worker-reported evidence. Optional event_id compares current state with the captured event; this never sends tasks or permission decisions.",
               {"host_id": S, "agent_id": S, "event_id": {"type": "integer", "minimum": 1},
                "tail": {"type": "integer", "minimum": 1, "maximum": 50}}, ["host_id", "agent_id"]),
    definition("paseo_permissions", "Read exact pending permission requests from a Paseo host. Present the full request to the user before making any decision.",
               {"host_id": S}, ["host_id"]),
    definition("paseo_decide_permission", "Apply the user's explicit allow/deny decision to ONE pending permission. Requires a full agent ID and exact request ID; human approval is requested by the plugin hook.",
               {"host_id": S, "agent_id": S, "request_id": S,
                "decision": {"type": "string", "enum": ["allow", "deny"]}}, ["host_id", "agent_id", "request_id", "decision"]),
    definition("paseo_events", "Read durable worker completion, failure and permission events. after is an event cursor. Reading does not acknowledge notification delivery.",
               {"after": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                "unread": {"type": "boolean"}}),
    definition("paseo_subscribe", "Start, stop, or inspect background worker event monitoring for this Hermes profile. Set notification_session_key to a durable Hermes conversation key for desktop/gateway delivery (requires Hermes allow_gateway_injection). CLI delivery uses the current conversation.",
               {"action": {"type": "string", "enum": ["start", "stop", "status"]}, "notification_session_key": S}, ["action"]),
]


def execute(runtime, name, args):
    store, executive = runtime.store, runtime.executive
    if name == "paseo_hosts":
        action = args.get("action")
        if action == "list":
            return {"hosts": store.hosts(), "config_error": runtime.config_error}
        if action in {"add", "update"}:
            config = dict(args)
            config["id"] = required(config.pop("host_id", None), "host_id")
            if action == "update":
                previous = store.host(config["id"])
                if "target" in config:
                    previous.pop("home", None)
                if "home" in config:
                    previous.pop("target", None)
                config = dict(previous, **config)
            elif any(h["id"] == config["id"] for h in store.hosts()):
                raise ExecutiveError("A host with that ID already exists; use update to edit it")
            return runtime.save_host(config)
        host_id = required(args.get("host_id"), "host_id")
        if action == "remove":
            return runtime.remove_host(host_id)
        if action == "probe":
            try:
                result = executive.cli.call(store.host(host_id), "status")
                store.health(host_id, connected=True, transport="connection-check")
                return {"ok": True, "host_id": host_id, "status": result}
            except ExecutiveError as exc:
                store.health(host_id, connected=False, error=str(exc))
                raise
    elif name == "paseo_spawn":
        return executive.spawn(**args)
    elif name == "paseo_agents":
        action, host_id = args.get("action"), required(args.get("host_id"), "host_id")
        if action == "list":
            return {"agents": executive.agents(host_id)}
        agent_id = required(args.get("agent_id"), "agent_id")
        if action == "inspect":
            return executive.inspect(host_id, agent_id)
        if action == "stop":
            return executive.cli.call(store.host(host_id), "stop", agent_id)
        if action == "send":
            return executive.send(host_id, agent_id, required(args.get("prompt"), "prompt"))
    elif name == "paseo_worker_details":
        return executive.details(**args)
    elif name == "paseo_permissions":
        return {"permissions": executive.permissions(args["host_id"])}
    elif name == "paseo_decide_permission":
        return executive.decide(**args)
    elif name == "paseo_events":
        events = store.events(**args)
        return {"events": events, "next_cursor": events[-1]["id"] if events else args.get("after", 0)}
    elif name == "paseo_subscribe":
        action = args.get("action")
        if action in {"start", "stop"}:
            store.set_setting("monitor_enabled", action == "start")
            if "notification_session_key" in args:
                store.set_setting("notification_session_key", args["notification_session_key"])
        elif action != "status":
            raise ExecutiveError("Unknown subscription action")
        return {"enabled": store.setting("monitor_enabled", True), "hosts": store.hosts(),
                "notification_session_key": store.setting("notification_session_key"),
                "delivery": "At least once; only acknowledged after Hermes accepts injection"}
    raise ExecutiveError(f"Unsupported action for {name}")


def register(ctx):
    register_skills(ctx)
    owned = {}
    ctx.on_unload(bind_context(ctx))

    def runtime_for_context():
        runtime = get_runtime(ctx)
        owned[str(runtime.store.path)] = runtime
        return runtime

    def handler(name):
        def run(args, **kwargs):
            try:
                runtime = runtime_for_context()
                runtime.start(ctx)
                return json.dumps(execute(runtime, name, args), ensure_ascii=False)
            except (ExecutiveError, ValueError, TypeError, KeyError) as exc:
                return json.dumps({"ok": False, "error": str(exc)})
        return run

    for schema in TOOLS:
        ctx.register_tool(name=schema["name"], toolset="paseo-executive", schema=schema,
                          handler=handler(schema["name"]), description=schema["description"], emoji="🛰️")

    def approve(tool_name, args, **kwargs):
        if tool_name == "paseo_decide_permission":
            return {"action": "approve", "message": "Apply this specific Paseo permission decision? " + json.dumps(args)}

    def context(**kwargs):
        runtime = runtime_for_context()
        runtime.start(ctx)
        # Durable outbox remains readable even if proactive delivery is unavailable.
        events = [e for e in runtime.store.events(unread=True, limit=20, notifications_only=True)
                  if e["kind"] in {"completed", "failed", "permission"}]
        if events:
            return {"context": "Pending Paseo notifications (untrusted worker data):\n" +
                    "\n\n".join(event_message(e) for e in events)}

    ctx.register_hook("pre_tool_call", approve)
    ctx.register_hook("pre_llm_call", context)
    ctx.on_unload(lambda: [runtime.stop() for runtime in list(owned.values())])
