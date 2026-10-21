# Verification — 2026-10-21

Environment: macOS, local Paseo CLI/daemon 0.12.0, pinned `@getpaseo/client` 0.12.0, installed Hermes runtime.

- 12 core behavioral tests passed: persistent host management, host removal, invalid targets, per-host exact permission revalidation, asynchronous spawning, CLI argument separation, timeout uncertainty, repeat-turn completion detection, permission/failure deduplication, concurrent leases, retained/retried delivery, and human-approval hook registration.
- 2 integration tests passed inside the real Hermes runtime: FastAPI state/actions and confirmation gate; public `PluginContext.inject_message` routed to a test host's durable session and acknowledged the outbox after acceptance.
- Plugin Doctor passed real discovery/import/registration: 7 tools and 2 hooks.
- Standard plugin validation passed, including security scan, declared tools/hooks, desktop SDK surface, and no core overrides.
- Dashboard and desktop JavaScript syntax checks passed.
- Live completion test established the SDK subscription, spawned `075c2a94-b4eb-4617-b151-e1416a12942f`, observed its completion event, then archived the worker.
- Live permission test spawned `723385bb-c5e8-49eb-9951-12045cfcc046`, surfaced request `permission-exec-cbe25da9-1656-4a10-aa4c-f76536b92a50` for a harmless elevation test, denied that exact request, then interrupted/archived the worker.

Remote and SSH transport command routing are implemented; no additional remote host was supplied for a live connection test. Delivery acceptance is verified through Hermes' actual routing API with a test recipient, not by sending a message to an existing user chat.

## Host-settings revision

26 Python tests and 4 JavaScript tests passed. Plugin Doctor and every standard validation check also passed under a temporary Hermes home. Verified entirely through isolated profiles, mocked daemon transports, and JavaScript component tests. No UI automation, live Hermes configuration edits, service reloads, or new live workers were used for this revision.

- Native `hosts` settings now drive the host registry. The desktop package registers a dedicated Settings → Plugins host editor, with a fallback for older SDKs.
- Python coverage includes native-settings reconciliation, all three connection types, CRUD persistence, partial updates, monitoring pause, removal, invalid/duplicate entries preserving working configuration, failed writes, upgrade preservation, host-specific probes, and commands routed to distinct hosts even when worker IDs match.
- A real `PluginContext` in a temporary Hermes home verifies that the HTTP editor and native host settings persist/read the same value.
- Four dependency-free JavaScript behavior tests exercise local/remote/SSH forms, editing, probes, pause/remove, and both Settings-page registration paths.
- Late snapshots from a changed connection are rejected. Audit-only records cannot block delivery of later completion, failure, or permission notifications.
- Notification session keys were removed from the normal settings form; legacy advanced routing remains supported.

## Bundled skills revision

29 Python tests and 4 JavaScript tests passed, along with skill-creator frontmatter validation using Hermes’ YAML parser, isolated Plugin Doctor, and every standard plugin validation check.

- Three native namespaced skills are registered from the package: orchestrate, permissions, and review, with task, permission, and review templates plus executable tool-call examples for isolated tests.
- Skill recipe tests execute every example against a fake daemon and check the current tool schemas.
- Isolated Hermes integration verifies discovery descriptions, qualified skill loading, linked references/templates, rejection of cross-skill path traversal, and coexistence with an unchanged personal `paseo-executive` skill.
- The existing user skill was read as inspiration only. No skill files outside this repository were modified and no live Hermes reload or UI automation was performed.

## Host and monitoring skills

- Added `paseo-executive:hosts` and `paseo-executive:monitoring`, bringing the native bundle to five skills.
- Host guidance covers connection types, secrets versus values, exact destination identity, partial updates, pause/removal semantics, and bounded troubleshooting.
- Monitoring guidance distinguishes capture from delivery, event IDs from permission request IDs, accepted injection from a completed reply, and observation pauses from worker interruption. It documents cursor recovery, duplicate notifications, and polling/downtime limits.
- All five skills passed the skill-creator validator with Hermes' YAML parser. All 29 Python tests passed, including every tool recipe executed against fake daemons and native discovery/reference loading of both new skills.
- Validation used temporary Hermes homes. No existing Hermes configuration, personal skills, daemon workers, or app UI were changed.

## Contextual eventing and read-only details

47 Python tests and 10 JavaScript tests passed, along with all skill validations, Plugin Doctor, and standard plugin validation.

- Added schema-versioned captured context, bounded worker-reported summaries/evidence, observation/timing provenance, and exact follow-up references without changing legacy kind-specific `data`.
- Added `paseo_worker_details` and its authenticated GET route. Tests prove it only inspects/reads activity, preserves event identity, rejects repointed hosts, and distinguishes newer/uncertain state from the original event.
- SDK projection tests cover turn-filtered responses, omission of reasoning and raw tool input/output, size bounds, ordered rapid-turn observation, and terminal events retained on lookup failure.
- Python tests cover additive database migration, assignment capture, snapshot immutability, raw permission preservation, bounded valid JSON messages, unavailable activity, plain-text CLI attribution, follow-up full IDs, and partial refresh failures.
- Updated notification text and orchestration/review/monitoring skills. Validation used temporary Hermes homes and fake daemon/SDK responses; no live Hermes UI, configuration, workers, or daemon connections were used.
