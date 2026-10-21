---
name: hosts
description: Configure and troubleshoot local, remote, and SSH Paseo daemon hosts through the Paseo Executive plugin. Use for adding or changing connections, checking reachability, pausing host monitoring, or safely removing a host.
---

# Manage Paseo hosts

Use `paseo_hosts` for host configuration and connection checks. These are the same profile-scoped records shown in Settings → Plugins → Paseo Executive and used by worker tools. Load [references/tool-recipes.json](references/tool-recipes.json) for supported argument examples. Examples are recipes to adapt, not instructions to modify the fleet automatically.

## Choose the right connection

List the registry first and identify the host by its unique `host_id`, label, and actual destination. Reuse an existing record when it already represents the intended daemon. A host label is not proof of which machine it controls.

| Connection | Configuration | What must be established |
| --- | --- | --- |
| Local daemon | `home`, such as `~/.paseo` | A daemon home on the machine running this Hermes profile |
| Remote daemon | `target`, such as `devbox:6767` or a Paseo pairing link | A reachable endpoint and the CLI's configured authentication |
| SSH host | `target: ssh://user@devbox` | Working SSH access through Paseo and the user's SSH configuration/keys |

Supply exactly one of `home` or `target`. A remote worker's `cwd` must exist on that remote host; a local checkout path is not automatically available there. Connection configuration does not clone repositories, create directories, provision machines, or start daemons.

Use a stable descriptive ID and an optional display label. For direct live-event connections, an optional `stream_url` must be a credential-free `ws://` or `wss://` URL. `password_env` names an existing Hermes-scoped secret for that event connection; never put the password itself in the host record. The CLI's own remote authentication is separate. Do not request, print, or copy private keys to diagnose a connection.

## Add, edit, check, or pause

Apply an already authorized connection change with `paseo_hosts` using `action: add` or `update`, then `probe` the same ID. An add requires an unused ID; use update for an existing record. An update can change one field or switch between `home` and `target`. Preserve unrelated hosts and fields. The native host-list editor replaces the entire configured list, so retain other entries when editing that list.

Probe results establish CLI reachability at the time of the check. They do not prove that providers are signed in, a particular project exists, or SDK event streaming is healthy. Read the host's recorded health and any error; stale health is historical evidence, not a current guarantee.

For a per-host monitoring pause, update `enabled: false`; resume with `enabled: true`. This affects observation, not the running workers or the ability to issue explicit worker commands. Use `paseo-executive:monitoring` for fleet-wide observation controls and notification diagnostics.

## Change a destination or remove a host safely

Before repointing or removing a host with active assignments, preserve their full agent IDs, original endpoint, directories, and outstanding decisions in the task record. Changing the destination changes where future commands go; it does not migrate existing workers. Do not reinterpret an old agent ID as a worker on the new daemon.

The host ID is the stable key. To rename that key, add a new record and remove the old one only within the user's requested scope; do not invent a rename command. `action: remove` stops monitoring that record without stopping its workers. Audit history is retained. Interrupt a worker only when that separate action is authorized.

## Troubleshoot from evidence

| Symptom | Useful next step |
| --- | --- |
| Unknown host or duplicate ID | List the registry and use the intended existing ID or a new unique one. |
| Invalid configuration | Correct the reported field. Invalid native host-list settings preserve the last working registry; check `config_error` rather than assuming the new destination took effect. |
| TCP/DNS/SSH failure | Probe the exact configured target; distinguish reachability, hostname, SSH user/key, and authentication errors. Do not silently fall back to local or another daemon. |
| Probe succeeds but spawning fails | Inspect the provider/directory error from that worker request. A daemon connection check does not test provider credentials or repository setup. |
| Probe succeeds but notifications fail | Use the monitoring skill to separate event capture from Hermes delivery. Avoid repeatedly editing a working host connection. |
| Host is paused | Resume its monitoring if requested; do not restart its daemon as a substitute. |

Use available read-only diagnostics on the intended host when needed and authorized. The plugin has no credential installer, SSH-key generator, daemon-restart, or network-exposure tool. Do not change those systems merely because a connection check failed. After a diagnostic pass and a targeted correction fail without new evidence, report the exact blocker and needed information rather than retrying indefinitely.
