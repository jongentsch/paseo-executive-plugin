---
name: orchestrate
description: Delegate coding tasks through the Paseo Executive plugin across local, remote, or SSH hosts, track asynchronous workers, and coordinate implementation and review. Use for requested Paseo delegation or status checks.
---

# Orchestrate Paseo workers

Act as the executive for coding work delegated to Paseo: clarify the outcome, assign workers, track evidence, and bring decisions back to the user. Delegate implementation to workers when using this workflow. Keep the brief focused on outcomes, constraints, and acceptance criteria; let workers choose implementation details unless the user or repository requires them.

Use the plugin's `paseo_*` tools. This bundle adapts the user's existing Paseo executive workflow to the plugin; it does not require shelling out to the CLI. For argument examples, load [references/tool-recipes.json](references/tool-recipes.json) with this skill's `file_path`.

## Select the host and scope

For host setup or connection troubleshooting, load `paseo-executive:hosts`.

Use `paseo_hosts` with `action: list` to resolve the intended host ID. Local, remote, and SSH hosts share the same tools; `cwd` always belongs to the selected host. A project path on this computer does not identify a checkout on another machine. Use the user's named host or an established task-to-host mapping; ask if the execution destination remains ambiguous. Do not silently move work to another host after a connection failure.

Probe a new or failing host with `paseo_hosts` using `action: probe`. Changing host configuration is separate from assigning work: add or edit hosts only when that is part of the user's request. Use the user's provider choice when supplied. Avoid hardcoded model versions or unsupported thinking/mode arguments.

## Dispatch asynchronously

Use [templates/worker-brief.md](templates/worker-brief.md) for a bounded assignment. Call `paseo_spawn` with `host_id`, `cwd`, `prompt`, and an optional `provider` and `title`. Spawning returns immediately; record the actual full agent ID and host ID before moving on. Do not busy-wait or run a long polling loop unless the user asked for active monitoring.

For capture, catch-up, or notification delivery issues, load `paseo-executive:monitoring`. Start or inspect event monitoring with `paseo_subscribe`. Completion, failure, and permission events are durable; use `paseo_events` for catch-up, carrying forward its returned `next_cursor`. Reading events does not acknowledge notification delivery. Filter events by the workers in the task ledger before interpreting them as this task's outcome.

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

## Session reuse over spawning

**Before spawning, always check for idle workers.** A worker with the right workspace (matching `cwd`) should receive follow-ups via `send`, not a new `spawn`. Spawning a new worker loses all accumulated context, memory, and open files. Only spawn when no idle worker has the needed workspace, provider, or when the task is completely unrelated to any idle worker's domain.

Reuse pattern:
1. List idle workers with `paseo_agents(action="list", host_id="...")`
2. Pick the worker whose `cwd` and provider match the task
3. Use `paseo_agents(action="send", host_id="...", agent_id="...", prompt="...")`
4. Spawn only if no suitable idle worker exists
5. **Record the full agent ID** of any worker you spawn — this is how you distinguish your workers from the user's, so you know what you can and cannot clean up

**Credit conservation:** Use `codex/gpt-6.1-sol` with `high` thinking level for most tasks. Reserve Opus only for complex orchestration or review work. Never use `ultra` or `xhigh` thinking unless the user explicitly requests it — it consumes credits exponentially.

**Reuse > cleanup.** Effective reuse means there is less need for cleanup. Keep long-lived idle workers around for their accumulated context. Only clean up when explicitly asked or when a worker is clearly stale.

## Check, recover, and hand off

Use `paseo_agents` with `action: inspect` for current worker state; use `send` for a scoped follow-up to that same `(host_id, agent_id)`. Check `paseo_permissions` independently of the worker's running/idle state. For pending requests load `paseo-executive:permissions`.

**Never ignore SDK events in hook output.** When Paseo completion, permission, or spawned events appear as [plugin hook output], act on them immediately:
- **Completion events** → load `paseo_worker_details`, report the actual result
- **Permission events** → surface to the user for decision (load `paseo-executive:permissions`)
- **Spawned events** → acknowledge and track in the task ledger
The SDK subscription delivers these directly to the conversation; ignoring them wastes the delivery mechanism and delays response.

On a spawn timeout or disconnect, the outcome may be unknown. List agents on the same host and inspect matching title/directory evidence before retrying; adopt the existing worker when its identity is established. Do not repeat a potentially successful mutation blindly. After a failed diagnostic and targeted recovery without new evidence, report the blocker instead of repeatedly spawning replacements.

Events include the known assignment/worker context and any bounded, unverified worker report. Use `paseo_worker_details` on the same host and full agent ID for a fresh read; pass the event ID for comparison with its captured state. An idle worker or a `completed` event means its turn ended, not that the assignment passed. Load `paseo-executive:review` to assess the result. Preserve partial work and evidence on failure. Stop a worker through `paseo_agents` with `action: stop` when the user requests interruption or the authorized task requires it; stopping and denying a permission are separate actions.

## Cleanup Procedure

**Worker reuse is the priority.** Effective reuse means there is less need for cleanup. Only clean up when explicitly asked or when idle workers have been idle for an extended period.

### Tracking owned workers

Record the full agent IDs of workers you spawn in the task ledger or conversation. When listing idle workers, distinguish between:
- **Your workers** — spawned by you during this session or previous sessions (recorded in your task ledger)
- **User's workers** — created by the user themselves

Never delete or archive a worker that the user created. You may only delete/archive workers you spawned.

### How to clean up (only when necessary)

1. **List ALL agents** — never filter to only idle: `paseo ls -a -g --json` and show full breakdown by status. Presenting partial data as complete is misleading.

2. **Filter to your workers** — cross-reference the agent list against your recorded task ledger. Only your workers are candidates for cleanup.

3. **Delete CLI agents** — use `paseo delete <id>` to hard-delete agents. **Never use `paseo stop`** — it is a no-op for idle agents (only interrupts running ones).

4. **Archive UI sessions** — use `paseo workspace archive <workspaceId>` to remove UI session entries. CLI delete removes agents but UI session entries persist independently (separate data sources).

5. **Verify** — run `paseo workspace ls --json` to confirm no stale entries remain.

### When to clean up

- User explicitly requests cleanup
- A long-lived worker is clearly stale (old test sessions, abandoned debugging)
- The user has indicated they are done with a worker and you did not record it as a long-lived worker

### When NOT to clean up

- The worker has context that could be useful for future reuse
- The user created the worker (never touch)
- You are not sure if the worker is yours or the user's
- Worker reuse is more valuable than a clean list
