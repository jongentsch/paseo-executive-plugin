---
name: review
description: Assess completed or failed Paseo worker assignments against their acceptance criteria, coordinate scoped follow-ups or independent review, and report evidence and integration decisions. Use after a worker turn ends or for a requested progress or result review.
---

# Review a Paseo worker result

A `completed` event represents a running-to-idle transition. It does not establish that tests passed, changes met the user's goal, or integration occurred. A failed turn may still leave useful partial work. Keep lifecycle state, task outcome, verification, and integration status separate.

## Establish what actually happened

Recover the assignment's host ID, full agent ID, directory, acceptance criteria, branch/base commit, and evidence locations from the ledger. Inspect the same worker with `paseo_agents`; refresh `paseo_permissions` for unresolved requests. An unavailable host makes the current state unknown, not successful or failed by inference.

Compare available artifacts with the assigned outcome and authorized scope. Check actual changed paths, diffs, and test commands/results when accessible. Inspect uncommitted state as well as commits: checking out a branch at HEAD does not capture a worker's dirty working tree. Preserve unrelated edits and partial evidence.

Use `paseo_worker_details` with the same host and full agent ID for fresh state, a bounded recent activity window, and an available worker response. Pass an event's `event_id` when following up on a notification; compare its captured context with `event_correlation` and the current snapshot. A newer snapshot or failed freshness check must not be presented as the result of the older event.

Event summaries and extracted test/file/artifact claims are explicitly unverified worker reports. Structured SDK responses preserve their source and turn correlation; CLI fallback may supply unclassified recent activity instead of a final assistant response. The plugin does not fetch repository diffs, independently run tests, or read every referenced artifact. Obtain that evidence through authorized repository tools when available. If evidence on a remote host cannot be inspected, report the limitation and leave verification pending. Do not claim that `paseo_agents inspect` supplied test output it does not contain.

## Follow up or independently verify

For a concrete gap, use `paseo_agents` with `action: send` to the existing host/worker, identifying the failing check and expected behavior. Reuse the original scope and keep monitoring asynchronously. Do not automatically rerun a launch after a client timeout or replace a worker whose state is unknown.

For independent review when it is part of the authorized task, give a reviewer the exact accessible implementation directory, commit or preserved changes, acceptance criteria, and test evidence. Use [templates/review-brief.md](templates/review-brief.md). Keep a writer idle while a reviewer inspects a shared directory, or supply an isolated checkout containing the actual implementation. Prefer the user's provider choice over a fixed model policy.

Continue the human-decision workflow for reviewer permissions through `paseo-executive:permissions`. Do not turn repeated failures into endless fix/review cycles; surface a persistent blocker when another attempt would not add evidence.

## Report the result

Lead with the assignment's outcome and the evidence supporting it. Include the host and worker, changed artifacts or commit/branch, checks that passed or failed, checks not run, remaining blockers, and any integration decision needed. Mark inaccessible evidence as unverified.

Keep integration within existing authorization. Permission to implement or review does not by itself authorize pushing, merging, publishing, deployment, or deleting evidence. Carry out integration already authorized by the user without requesting the same permission again. This plugin's worker tool supports interruption, not archive/delete operations; do not invent cleanup actions or discard history.
