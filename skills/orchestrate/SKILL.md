---
name: orchestrate
description: Delegate coding tasks through the Paseo Executive plugin across local, remote, or SSH hosts, track asynchronous workers, and coordinate implementation and review. Use for requested Paseo delegation or status checks.
---

# Orchestrate Paseo workers

Act as the executive for coding work delegated to Paseo: clarify the outcome, assign workers, track evidence, and bring decisions back to the user. Delegate implementation to workers when using this workflow. Keep the brief focused on outcomes, constraints, and acceptance criteria; let workers choose implementation details unless the user or repository requires them.

Use the plugin's `paseo_*` tools. This bundle adapts the user's existing Paseo executive workflow to the plugin; it does not require shelling out to the CLI. For argument examples, load [references/tool-recipes.json](references/tool-recipes.json) with this skill's `file_path`.

## Select the host and scope

Use `paseo_hosts` with `action: list` to resolve the intended host ID. Local, remote, and SSH hosts share the same tools; `cwd` always belongs to the selected host. A project path on this computer does not identify a checkout on another machine. Use the user's named host or an established task-to-host mapping; ask if the execution destination remains ambiguous. Do not silently move work to another host after a connection failure.

Probe a new or failing host with `paseo_hosts` using `action: probe`. Changing host configuration is separate from assigning work: add or edit hosts only when that is part of the user's request. Use the user's provider choice when supplied. Avoid hardcoded model versions or unsupported thinking/mode arguments.

## Dispatch asynchronously

Use [templates/worker-brief.md](templates/worker-brief.md) for a bounded assignment. Call `paseo_spawn` with `host_id`, `cwd`, `prompt`, and an optional `provider` and `title`. Spawning returns immediately; record the actual full agent ID and host ID before moving on. Do not busy-wait or run a long polling loop unless the user asked for active monitoring.

Start or inspect event monitoring with `paseo_subscribe`. Completion, failure, and permission events are durable; use `paseo_events` for catch-up, carrying forward its returned `next_cursor`. Reading events does not acknowledge notification delivery. Filter events by the workers in the task ledger before interpreting them as this task's outcome.

Give a brief dispatch acknowledgement identifying the host, worker, and goal. Continue independent work or return control to the user. A background task can outlive this conversation. Automatic proactive notification needs a live authorized Hermes delivery route; do not promise delivery to an unspecified chat. If delivery is unavailable, retain the pending events and surface them on the next interaction.

## Coordinate workers

For independent assignments, give writers separate existing worktrees or disjoint ownership. Record shared contracts and dependencies; launch ready work without waiting on unrelated tasks. Start dependent work only after its input artifacts are verified. A second worker on the same host and directory does not gain filesystem isolation automatically.

The plugin does not create worktrees, branches, schedules, or repositories. Arrange isolation through separately authorized repository tooling when available, or ask for suitable directories. Do not invent `workspace`, `new_branch`, `thinking`, `background`, or timeout arguments for `paseo_spawn`.

Track this task record in the conversation or an already authorized durable task store:

- Outcome, acceptance criteria, and scope.
- Host ID, full agent ID, provider, and host-side working directory.
- Workspace/branch/base commit if established, file ownership, and dependencies.
- State, event cursor, pending request IDs, evidence locations, and next decision.

An external memory service is optional, not a dependency of this skill.

## Check, recover, and hand off

Use `paseo_agents` with `action: inspect` for current worker state; use `send` for a scoped follow-up to that same `(host_id, agent_id)`. Check `paseo_permissions` independently of the worker's running/idle state. For pending requests load `paseo-executive:permissions`.

On a spawn timeout or disconnect, the outcome may be unknown. List agents on the same host and inspect matching title/directory evidence before retrying; adopt the existing worker when its identity is established. Do not repeat a potentially successful mutation blindly. After a failed diagnostic and targeted recovery without new evidence, report the blocker instead of repeatedly spawning replacements.

An idle worker or a `completed` event means its turn ended, not that the assignment passed. Load `paseo-executive:review` to assess the result. Preserve partial work and evidence on failure. Stop a worker through `paseo_agents` with `action: stop` when the user requests interruption or the authorized task requires it; stopping and denying a permission are separate actions.
