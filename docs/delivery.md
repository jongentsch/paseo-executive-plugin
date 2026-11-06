# Conversation delivery

SDK capture, UI broadcasts, and conversation delivery are separate operations. Reading `paseo_events` does not acknowledge an event.

The `pre_llm_call` hook claims pending completion, failure, and permission events, returns their bounded messages as Hermes conversation context, and acknowledges that handoff. Proactive delivery acknowledges only a successful `ctx.inject_message` call. Broadcast failures do not block injection. Failed injection releases its claim so the next conversation hook can deliver it immediately; the supervisor retries on its next iteration.

`notification_session_key: desktop` is a plugin destination alias. Calling `paseo_subscribe` with `action: start` from the intended desktop conversation binds its actual Hermes session key. The first desktop hook can also establish an unbound destination. Other desktop conversations cannot consume an already bound subscription; explicitly subscribe from a new conversation to move it. Subscription status exposes `resolved_notification_session_key`. Until a conversation is bound, events remain pending.

Proactive desktop/gateway injection requires `plugins.entries.paseo-executive.allow_gateway_injection: true` in Hermes config. A rejected injection retains the event for the next matching conversation hook. A hook handoff means Hermes accepted context, not that a model response or UI render has completed.

Run regression tests with the Hermes environment Python: `python -m unittest discover -s tests -p 'test_*.py'`. Run `python -m tests.live_delivery` for an opt-in local worker test using real SDK snapshots and real Hermes hook dispatch with an isolated database and hook session. That smoke test does not verify rendering in an existing desktop conversation.
