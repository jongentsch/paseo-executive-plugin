---
name: monitoring
description: Monitor Paseo worker events and diagnose notification delivery through the Paseo Executive plugin. Use for enabling or pausing observation, catching up after disconnection, duplicate notifications, or events that have not reached Hermes.
---

# Monitor workers and deliver notifications

Separate worker state, event capture, and notification delivery. A working daemon connection does not prove that events are being observed or that Hermes has an authorized destination. Use the plugin tools and [references/tool-recipes.json](references/tool-recipes.json) for operational checks. Keep diagnosis scoped to the requested connections and delivery behavior.

## Establish observation

Inspect `paseo_subscribe` with `action: status` and `paseo_hosts` with `action: list`. Check the global observation flag, the relevant hosts' `enabled` values, health timestamps, transport, and errors. Start observation with `paseo_subscribe` using `action: start` when requested or as part of an authorized asynchronous assignment. Each host also needs its own monitoring enabled.

The plugin starts monitoring lazily after a tool call, Hermes turn, or dashboard request, and monitoring runs in Hermes' plugin process. Loading the skill or merely having the plugin installed does not prove that a monitor is running. `status` reports configuration and last recorded health, not an end-to-end delivery test.

Local TCP daemons can use live SDK subscriptions. Remote hosts with a configured direct SDK URL can do the same; SSH, pairing, socket, or other hosts without that connection use CLI polling. The normal polling interval is about 10 seconds plus command time; reconnect failures back off to about 60 seconds. Live subscriptions also reconcile periodically. Pauses, process downtime, and polling can miss an entire short running-to-idle cycle. Reconnection reconciles observed state; do not promise complete historical event replay for an unobserved interval.

## Catch up without replaying work

Read `paseo_events` from the task's last recorded integer cursor, carrying its returned `next_cursor` forward on every page, including pages with unrelated events. Use a bounded page size; do not assume an empty filtered result means all workers are done. On a resumed session with no cursor, start at zero and correlate relevant records against the task ledger.

Event rows use `host` and `agent`; pass these as tool arguments `host_id` and `agent_id`. The outer integer `id` is the event cursor/notification identity, not a permission request ID. A permission event's exact request is in its `data`; refresh `paseo_permissions` before acting and load `paseo-executive:permissions` for the user-decision workflow.

| Event | Interpretation |
| --- | --- |
| `spawned` | Worker creation audit record; not completion or success. |
| `completed` | A running-to-idle transition was observed; load `paseo-executive:review` to assess the result. |
| `failed` | An error state or changed last error was observed; preserve partial work and inspect the worker. |
| `permission` | A request needs attention; it is not authorization to approve. |
| `permission_resolved` | A permission decision was recorded; it does not establish task completion. |

Read current worker state on the same host when event history is incomplete. Never repeat a spawn, send, or permission decision just to regenerate a missing notification.

## Distinguish capture from delivery

If an expected event is absent, check the relevant host's monitoring, last health, current worker state, and transport limitations first. Use `paseo-executive:hosts` for connection troubleshooting. An absent event alone is not proof that the worker is still running or that it failed.

If the event exists but no notification arrived, inspect unread events and the delivery route. Only completion, failure, and permission events are proactively delivered. `spawned` and `permission_resolved` audit records may remain marked undelivered; do not treat that as a notification failure. Reading an event does not acknowledge it, and the tools expose no manual acknowledge/requeue/delete operation.

CLI conversation injection can use its attached session. Desktop/TUI or messaging conversation injection needs a live authorized Hermes route. `paseo_subscribe` can store a known durable `notification_session_key`, but does not create a conversation or grant `allow_gateway_injection`. A missing stored key alone does not diagnose CLI routing or a route configured elsewhere. Do not guess a destination from a visible tab ID or silently choose another recipient. If route setup is needed, explain the missing route/grant and use the user's established destination; changing a grant or app notification preferences is a separate authorized setup action.

Desktop notifications, accepted conversation injection, and a completed Hermes reply are distinct observations. The delivery flag records that Hermes accepted injection, not that a model turn finished or the user saw a notification. If no authorized route is available, leave notifications pending, report the limitation, and surface them on the next interaction rather than claiming successful proactive delivery.

## Recover and pause deliberately

Notifications are delivered at least once. A crash after Hermes accepts an event but before acknowledgement can repeat the same event ID. Deduplicate within the same profile using that stable ID and retain the host/worker context. Different event IDs may represent separate turns; do not suppress them merely because their wording matches. Refresh current pending permissions rather than reapplying a decision from a repeated notification.

To pause observation for the fleet, use `paseo_subscribe` with `action: stop`; for one host, update its `enabled` value through `paseo_hosts`. These actions do not stop coding workers, erase history, revoke a notification route, or necessarily stop delivery of events already in the outbox. Resume observation explicitly when requested. Do not clear plugin data, restart Hermes, or recreate workers as a notification repair shortcut.

After a bounded diagnostic pass, report the affected host/worker, last event/cursor and health time, whether the issue is capture or delivery, available evidence, and the specific remaining blocker. Avoid repeated retries without new evidence.
