# Contextual events and follow-up reads

Notifications use an additive `schema_version: 1` envelope. Existing `id`, `host`, `agent`, `kind`, `data`, `created`, and delivery-bookkeeping fields remain. `data` retains the original kind-specific shape, including the exact permission request. New fields provide captured context, an explicitly unverified result, and a read-only follow-up reference.

A completion can look like this (values are illustrative; unavailable fields are null or omitted):

```json
{
  "schema_version": 1,
  "id": 42,
  "host": "linux",
  "agent": "full-agent-uuid",
  "kind": "completed",
  "data": {"status": "idle", "name": "Login fix"},
  "context": {
    "host_label": "Linux worker",
    "connection_key": "hash-of-connection-identity",
    "worker": {"name": "Login fix", "provider": "codex", "model": null, "cwd": "/srv/project", "workspace_id": null, "branch": "fix/login"},
    "assignment": {"prompt": "Fix the login redirect", "assigned_at": 1792590000.0},
    "timing": {"started_at": 1792590001.0, "observed_at": 1792590020.0, "elapsed_seconds": 19.0, "basis": "daemon"},
    "observation": {"source": "sdk", "snapshot_updated_at": "2026-10-21T13:40:20Z", "turn_id": "turn-uuid", "sequence": 1, "snapshot_revision": 3}
  },
  "result": {
    "summary": "Fixed the redirect and ran the login tests",
    "source": "paseo_sdk_timeline",
    "scope": "turn",
    "attribution": "worker_reported",
    "verification": "not_verified",
    "reported_evidence": {"reported_passed": true, "tests": ["pytest tests/login: passed"], "changed_files": ["login.py"], "artifacts": ["reports/login.txt"]},
    "truncated": false
  },
  "follow_up": {"tool": "paseo_worker_details", "arguments": {"host_id": "linux", "agent_id": "full-agent-uuid", "event_id": 42}},
  "created": 1792590020.0,
  "delivered": 0,
  "claimed_until": 0.0
}
```

## What is captured

- Plugin-launched workers record a bounded assignment prompt, title, requested provider, and working directory. Accepted follow-ups are recorded against the resolved full worker ID. Assignments are selected against the observed turn's start; externally launched workers can have no known assignment.
- Worker identity comes from the snapshot, with known assignment fields as fallback. Model, workspace, and branch are included only when available. No repository scan, diff read, or test execution is performed for event enrichment.
- Turn IDs and daemon start times are used when available. Otherwise timing is based on observation. Observed duration may cover only the visible part of a turn; daemon-based estimates assume the machines' clocks agree. A completion records an observed lifecycle transition, not verified task success.
- SDK timeline reads preserve assistant-message identity and turn correlation. Structured JSON replies can expose `tests`, `changed_files`, `artifacts`, and `passed` as **worker-reported claims**. Prose is kept as a summary, not guessed into structured evidence.
- The CLI fallback reads a bounded log tail. Some CLI versions render plain text even with `--json`, so this is labeled `unclassified_activity` / `recent_activity` rather than a final assistant response. It can contain user/tool text as well as worker output.

The SDK watcher serializes snapshots per worker while an optional result lookup runs. It limits that lookup to two seconds; failure still emits the terminal snapshot with an unavailable-summary reason. Newer snapshot versions or mismatching turn IDs prevent an unrelated report from being promoted to the captured result. CLI polling similarly checks freshness around its activity read. Captured event metadata does not change when a later worker turn starts.

## Read-only details tool

```json
{"host_id":"linux","agent_id":"full-agent-uuid","event_id":42,"tail":20}
```

`paseo_worker_details` performs inspection and activity/timeline reads only. It does not send prompts, alter permissions, interrupt workers, run tests, or modify repositories. `event_id` is optional; `tail` is an integer from 1 to 50.

The result includes:

| Field | Meaning |
| --- | --- |
| `snapshot` | Freshly read, bounded worker state and pending-request information |
| `snapshot_truncated` | Whether snapshot content was bounded; use the exact permissions tool before deciding a request |
| `snapshot_observed_at` | Time of the returned snapshot read |
| `assignment` | Latest known plugin assignment |
| `activity` | Bounded recent SDK entries or CLI log text, with source/scope and truncation information |
| `result` | An available unverified worker report or unavailable reason |
| `event` | The original captured event when requested |
| `event_correlation` | `same_snapshot`, `newer_snapshot`, `unknown`, or `not_requested` |
| `state_freshness` | `refreshed`, or `second_read_failed` if a subsequent freshness read failed |
| `verification` | Always `not_verified`; Hermes still needs evidence checks before declaring success |

An event ID must match the same host and full agent ID. If the host connection changed since capture, the tool refuses to query that replacement daemon. If a worker advances while activity is fetched, the potentially misattributed report is discarded and the newer state is returned separately. A second-read failure returns the last observed snapshot with explicit uncertainty. A first inspection failure reports the read error; the original event remains available through `paseo_events`.

The same operation is available as authenticated `GET /api/plugins/paseo-executive/workers/<host_id>/<agent_id>/details?tail=20&event_id=42` or through the existing `/action` endpoint.

## Bounds and delivery

Assistant text/activity is bounded to roughly 12,000 characters per read, with summaries capped at 2,400 characters. Extracted evidence lists include at most 12 items of 400 characters each. Assignment prompts retain at most 4,000 characters and expose a truncation flag. Structured SDK projection excludes reasoning and raw tool inputs. Completion and failure envelopes include bounded canonical tool results in `result.tool_results` (shell output and exit codes, file paths and diffs/content, and other SDK result details), plus `result.response` when an assistant response is available. Tool-only turns retain their results even without an assistant response. Permission event `data` remains exact; conversation messages use valid bounded JSON and a follow-up reference when full detail is needed.

Hermes' event bus receives the contextual event envelope. Conversation injection receives the identity, bounded context/result/data, a follow-up reference, and an instruction to treat worker content as untrusted and unverified. Desktop notifications use the worker's title plus a short worker-report or recent-activity excerpt. No model call is made to summarize events.

Existing at-least-once delivery and cursor semantics apply. Reading details or events does not acknowledge delivery. Permission events still require a fresh exact-request check and the user's decision. Legacy databases migrate additively; old events without captured context report it as unavailable rather than substituting today's snapshot.
