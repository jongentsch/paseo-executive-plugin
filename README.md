# Paseo Executive for Hermes

A native Python **Hermes plugin** that lets Hermes oversee asynchronous Paseo coding workers. Install it in `~/.hermes/plugins/paseo-executive/`. It uses the installed Paseo CLI for control and the supported `@getpaseo/client` SDK for live events.

- Register local daemon homes, remote endpoints, and `ssh://user@host` targets.
- Spawn workers and return their IDs immediately; inspect, follow up, or interrupt them later.
- Show exact permission requests and apply a user decision to one request on one host.
- Subscribe to agent snapshots, permission requests, and attention events.
- Persist completion, failure, and permission events, then deliver them to Hermes for notification.
- Manage hosts, workers, approvals, and activity in a dashboard tab and desktop pane.

This is the Hermes integration described by the brief, using `plugin.yaml` and `register(ctx)`. It is installed by Hermes, rather than by the separate `paseo plugin install` daemon-extension system.

## Install

Requires Python 3.11+, Node.js 22+, npm, a working Paseo CLI, and Hermes with the documented native plugin/desktop SDK. Tested with Paseo CLI, daemon, and client SDK **0.12.0** and the installed October 2026 Hermes build.

```sh
git clone <your-repository-url> paseo-executive-plugin
cd paseo-executive-plugin
./scripts/install.sh
hermes plugins doctor . --ci
hermes plugins enable paseo-executive
```

For a local checkout, just run `./scripts/install.sh`. It installs the lockfile-pinned SDK with lifecycle scripts disabled and links the checkout into the selected `$HERMES_HOME/plugins/`. It refuses to overwrite another plugin. The Python backend uses FastAPI, declared in `pyproject.toml` and `plugin.yaml`; Hermes manages Python dependency admission when enabling.

**Settings → Plugins → Paseo Executive** is the host-management page. Its desktop editor has **Add host**, **Edit**, **Check connection**, **Pause/Resume monitoring**, and **Remove** controls. Choose **Local daemon**, **Remote daemon**, or **SSH host**; each type shows its relevant connection fields. The package also contributes a **Paseo Executive** worker pane.

The native Python settings form provides a **Paseo hosts** JSON list as well, so multiple hosts can be configured without the desktop UI extension. It accepts the same entries shown below. The form and editor persist the same profile-scoped `hosts` setting; the running monitor reconciles changes without a restart. The CLI executable override remains an advanced option. Notification session identifiers are not required to manage hosts and are no longer shown in the normal settings form. The web dashboard adds a **Paseo Executive** tab. The desktop half and Python half have separate enable switches; both must be enabled for the pane to reach the backend. Dashboard routes use Hermes' existing authentication and plugin enable gates.

## Ask Hermes

> Add my SSH host ssh://jon@linux-worker, then delegate the failing tests in /srv/project to a Codex worker there. Tell me when it finishes and bring me any permission requests.

The eight tools are:

| Tool | Purpose |
| --- | --- |
| `paseo_hosts` | List, add, update, remove, or probe daemon hosts |
| `paseo_spawn` | Start a worker asynchronously with a prompt, host, provider, and host-side working directory |
| `paseo_agents` | List, inspect, send a task to, or interrupt workers |
| `paseo_worker_details` | Read fresh worker state, bounded activity/response, and unverified reported evidence; optionally compare with a captured event |
| `paseo_permissions` | Retrieve exact pending requests |
| `paseo_decide_permission` | Apply an explicit allow/deny decision to one request |
| `paseo_events` | Read the durable event stream using an integer cursor |
| `paseo_subscribe` | Start, pause, or inspect monitoring and set its notification route |

For the native **Paseo hosts** setting, use a list such as:

```json
[
  {"id":"local","label":"This Mac","home":"~/.paseo","enabled":true},
  {"id":"linux","label":"Linux worker","target":"ssh://jon@linux-worker","enabled":true},
  {"id":"windows","label":"Windows worker","target":"192.0.2.20:6767","enabled":true}
]
```

IDs must be unique. Saving `[]` removes all hosts. Invalid entries preserve the last working registry and surface a configuration error. Existing host records are preserved when upgrading from a version without a `hosts` setting. Pausing a host stops its monitor; removing it does not stop its workers. Editing a connection invalidates old snapshots and rejects late events from that connection.

Example arguments for `paseo_hosts`:

```json
{"action":"add","host_id":"linux","target":"ssh://jon@linux-worker"}
{"action":"add","host_id":"lan","target":"10.0.0.10:6767"}
{"action":"add","host_id":"other-local","home":"/absolute/path/to/.paseo"}
```

SSH uses Paseo's SSH transport and the user's existing SSH configuration. No shell command strings or interpolated remote commands are constructed by the plugin. Remote paths belong to the selected daemon host. Removing a host disconnects monitoring; its workers continue running. Existing worker and event records remain available for audit.

## Bundled skills

The plugin registers five read-only Hermes skills through the native `ctx.register_skill()` API:

| Qualified skill | Purpose |
| --- | --- |
| `paseo-executive:hosts` | Configure and troubleshoot local, remote, and SSH hosts; safely edit/remove destinations and pause individual monitors |
| `paseo-executive:monitoring` | Observe events, recover cursors, diagnose capture versus delivery, and handle duplicate/pending notifications |
| `paseo-executive:orchestrate` | Delegate asynchronously across hosts, maintain task identity, coordinate workers, and recover without duplicate launches |
| `paseo-executive:permissions` | Present a precise request and apply the user's host/agent/request-specific decision |
| `paseo-executive:review` | Assess evidence, coordinate follow-ups or independent review, and report verified outcomes |

Discover them with `skills_list(category="plugin")` and load one with `skill_view("paseo-executive:orchestrate")`. The host, monitoring, and orchestration skills include tool-call recipes; orchestration also has a worker-brief template; permissions and review include their own decision/review templates. Read a linked resource through the same qualified skill, for example `skill_view("paseo-executive:orchestrate", file_path="references/tool-recipes.json")`.

These are inspired by the user's existing personal `paseo-executive` skill: async delegation, task ledgers, isolated writers, exact permission decisions, and evidence-based review. The bundle uses the plugin's actual tools, makes unsupported workspace/log operations explicit, and does not pin provider model versions or repeat obsolete CLI flags.

Namespacing keeps the existing bare `paseo-executive` skill separate. Plugin skills stay in this repository; registration does not copy into or replace the user's skill tree. They are available when the plugin is enabled and follow its normal load/unload lifecycle. This update does not change an existing Hermes session or reload its plugins.

## Events and notifications

Monitoring starts lazily on the first tool call, Hermes turn, or dashboard request and continues in the host process until paused or unloaded. The default host is the local `~/.paseo` daemon.

For local TCP daemons, the plugin discovers the published endpoint through `paseo status`, authenticates with the daemon's local credential, and establishes owned SDK subscriptions. The SDK reconnects and restores subscription snapshots; the plugin also reconciles through the CLI every 60 seconds. Multiple agent catalog pages are subscribed. Runtime changes to a host replace its monitor.

For a remote host, optionally set `stream_url` (for example `wss://worker.example/ws`) and `password_env` (the name of a Hermes-scoped secret, not its value). Configure the CLI's own remote authentication separately. SSH, pairing links, Unix sockets, and hosts without a direct SDK endpoint use CLI snapshot polling, normally every 10 seconds. That fallback detects observed state changes; a full running-to-idle cycle entirely between polls can be missed. Use a reachable SDK endpoint/tunnel when every short turn matters. Network failures back off to 60 seconds and retain pending notifications. Node/SDK absence also falls back to CLI monitoring.

Snapshots, host configuration, events, cursors, and delivery leases live in the active profile's `plugin-data/paseo-executive/executive.sqlite3`, outside the install tree. The database is created with user-only permissions. Concurrent Hermes/dashboard processes coordinate host monitors and outbox delivery through SQLite leases.

Contextual notifications include the known assignment, worker/provider/host/directory, available workspace/branch, turn timing, and observation provenance. A bounded worker response or activity excerpt is included when available; structured test/file/artifact claims remain explicitly unverified. Each event links to the read-only `paseo_worker_details` tool for targeted follow-up. Captured context stays separate from newer worker state. See [Event payloads and read-only details](docs/eventing.md) for the full contract and transport limits.

Events include `completed` (running → idle), `failed` (error status or changed last error), and `permission` (a new exact request ID). The first idle snapshot creates a baseline, not a spurious completion notification. `spawned` and `permission_resolved` provide audit records. Repeated identical snapshots do not duplicate events; separate turns can complete repeatedly.

Hermes receives events through public `ctx.emit`, `broadcast_plugin_event`, and `ctx.inject_message`. The desktop half shows toast and OS notifications. The model receives contextual event data marked as untrusted, unverified worker content and is instructed to notify the user. In CLI sessions, injection routes to the attached conversation automatically.

Desktop/TUI and messaging sessions need a **durable Hermes session key** plus this existing Hermes grant in the owning profile's `config.yaml`:

```yaml
plugins:
  enabled: [paseo-executive]  # preserve other enabled plugins
  entries:
    paseo-executive:
      allow_gateway_injection: true
      settings:
        notification_session_key: "<durable Hermes session key>"
```

This is an advanced notification-routing option for unattended conversations, separate from host setup. You can also set the route with `paseo_subscribe`. The plugin does not guess a messaging recipient or enable the injection grant. Without a live authorized route, events remain in the outbox, appear in the UI, and are surfaced as context on the next Hermes turn. Delivery is **at least once**: an event is acknowledged only when Hermes accepts injection, not when a downstream model turn finishes. A crash after acceptance but before acknowledgement can repeat an event; each notification carries its stable event ID.

## Permission handling

The `pre_tool_call` hook sends `paseo_decide_permission` through Hermes' human approval gate. The desktop/dashboard buttons submit a direct user decision; the HTTP endpoint requires `user_confirmed: true`. Before responding, the backend refreshes the same host and full agent ID and verifies that the exact request is still pending. It does not approve all requests or switch workers into a permission bypass mode. Paseo/provider approval policy still governs the worker.

CLI operations use argument vectors, explicit host selectors, `--json`, bounded timeouts, and a positional separator for prompts. Timed-out mutations report an unknown outcome and are not automatically retried. This plugin runs with the user's trusted plugin privileges, like other native Hermes plugins.

## Develop and verify

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/hosts_ui.test.cjs
hermes --run-module unittest discover -s tests -p test_hermes_integration.py -v
python3 scripts/build_ui.py
node --check dashboard/dist/index.js
node --check desktop/plugin.js
hermes plugins doctor . --ci
hermes plugins validate .
```

For development, run Hermes integration tests with a temporary `HERMES_HOME`; they use fake connection responses and never require an existing Hermes session or live Paseo worker.

The UI build is a tiny Python generator: plain React JavaScript, no bundler or bundled React. The desktop uses Hermes' shared React Query cache and event stream. Both surfaces call the same FastAPI routes and orchestration service.

Opt-in live tests spawn disposable workers on the default local daemon and archive them afterward:

```sh
python3 -B tests/live_smoke.py
python3 -B tests/live_permission_smoke.py
```

The first worker only replies to a no-tools prompt; it verifies SDK subscription, asynchronous spawning, and completion detection. The second explicitly requests elevation for `/usr/bin/true`; the harness denies that exact request and verifies the permission event. See [VALIDATION.md](VALIDATION.md) for this installation's results.

## Layout

```text
plugin.yaml                  Hermes metadata, tools, hooks, settings form
skills/                      Namespaced host, monitoring, orchestration, permission, and review guidance
__init__.py                  Native plugin registration
paseo_executive/core.py       Host/worker/permission service and durable storage
paseo_executive/runtime.py    Background subscriptions, reconciliation, delivery
paseo_executive/api.py        Shared FastAPI backend
plugin_api.py                Root backend entrypoint
dashboard/plugin_api.py      Dashboard backend entrypoint
dashboard/dist/index.js      Prebuilt dashboard UI
desktop/plugin.js            Native host settings, worker pane, notifications
frontend/hosts.js            Shared connection-type-aware host editor
bridge/details.mjs           Bounded read-only SDK timeline lookup
bridge/watch.mjs             Supported Paseo SDK subscription → contextual snapshot JSONL
scripts/install.sh           Reproducible SDK installation and linked deployment
```
