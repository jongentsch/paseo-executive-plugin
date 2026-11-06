# Cron Event Polling for Background Notifications

Use when SDK-based event delivery (e.g., `paseo_subscribe`) captures events but they never reach the agent's conversation. This is the practical workaround for Hermes' known gap: notices queue at turn start, not mid-turn, and the daemon does not interrupt a running turn with external notifications.

## Pattern

Create a `--no-agent` cron job that polls for new undelivered events and delivers to Bot Chat.

```bash
hermes cron create "every 2m" \
  --name "Event Poller" \
  --script event_poll.py \
  --deliver bot-chat:default \
  --no-agent
```

- `--no-agent` — no LLM run; script stdout is delivered verbatim
- `--deliver bot-chat:default` — injects into the default profile's Bot Chat
  - **When idle** → triggers a new turn (agent processes the notification)
  - **When mid-turn** → Hermes queues delivery (processed after turn completes)
- `--name` — used to derive the notepad path for dedup (`~/.hermes/cron/<job_id>/notepad`)

## Dedup with cron notepad

The script must only output when there are **new** undelivered events. Track the last-delivered event ID in the cron notepad:

```python
NOTEPAD = Path.home() / '.hermes/cron/<job_id>/notepad'

def get_last_delivered_id():
    if NOTEPAD.exists():
        return json.loads(NOTEPAD.read_text()).get('last_delivered_id', 0)
    return 0

def save_last_delivered_id(eid):
    NOTEPAD.parent.mkdir(parents=True, exist_ok=True)
    last = get_last_delivered_id()
    if eid > last:
        NOTEPAD.write_text(json.dumps({'last_delivered_id': eid}))
```

Query events newer than `last_delivered_id`. When the script outputs, save the highest event ID seen.

When the script finds **no** new events but old undelivered events still exist (from before tracking started), reset `last_delivered_id` to 0 so they are not missed.

## Script structure

```python
#!/usr/bin/env python3
import sys, json, sqlite3
from pathlib import Path

HOME = Path.home()
DB = HOME / '.hermes/plugin-data/<plugin>/executive.sqlite3'
NOTEPAD = HOME / '.hermes/cron/<job_id>/notepad'

def main():
    events = get_new_events()  # query DB with last_delivered_id filter
    if not events:
        stale = check_stale_events()  # any events at all?
        if stale:
            save_last_delivered_id(0)  # reset to catch up
        sys.exit(0)

    max_id = max(e.id for e in events)
    save_last_delivered_id(max_id)

    msg = "Pending events:\n" + "\n".join(format(e) for e in events)
    print(msg)
```

## Why this works

Hermes queues cron output to Bot Chat. When the agent is idle, the queued output triggers a new turn. When the agent is mid-turn, the output is queued and delivered after the turn ends. This avoids mid-turn interruption while still waking the agent when idle — which is the desired behavior for background notifications.

The dedup ensures the cron only notifies on genuinely new events, preventing repeated spam from stale undelivered audit records (e.g., `spawned` events that are not proactively delivered by design).

## Pitfalls

- **Use the job's actual UUID** for the notepad path. Run `hermes cron list` to find it.
- **Script must exit silently (no output, exit 0)** when there are no new events. Any stdout is delivered to Bot Chat.
- **Stale events from before tracking** — if the database has undelivered events from before the notepad was created, reset `last_delivered_id` to 0 so the script will output them once.
- **`spawned` events are not notifications** — `spawned` and `permission_resolved` may remain undelivered by design; only `completed`, `failed`, and `permission` are proactively delivered. The dedup handles this naturally.
- **After plugin source changes, reload the plugin** (`hermes plugins disable/enable`) for event delivery fixes to take effect. The cron script reads the database directly and does not depend on the plugin being loaded.
