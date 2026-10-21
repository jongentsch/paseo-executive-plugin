# AGENTS.md — Paseo Executive Plugin

This project is the Paseo Executive Plugin for Hermes Agent.
It is a Python plugin that makes Hermes an executive assistant for managing Paseo coding workers.

## How to Build
1. Create the plugin directory structure at `~/.hermes/plugins/paseo-executive/`
2. Implement all capabilities from REQUIREMENTS.md
3. Test on local Paseo daemon first
4. Deploy to `~/.hermes/plugins/paseo-executive/`
5. Ensure plugin.yaml is correct
6. Verify it appears in Settings → Plugins

## Key Files
- `plugin.yaml` — metadata and permissions
- `plugin_api.py` — FastAPI backend (core orchestration logic)
- `dashboard/plugin_api.py` — dashboard backend
- `dashboard/dist/` — frontend (simple HTML/JS dashboard)
- `desktop/plugin.js` — desktop UI pane

## Paseo CLI Reference
- CLI at: `/Applications/Paseo.app/Contents/Resources/bin/paseo`
- Commands: ls, run, inspect, send, attach, stop, archive, delete, permit ls, heartbeat, script, hooks
- For remote hosts: use `--host ssh://user@host` or `--host <ip>:6767`

## Testing
After building:
1. Verify `~/.hermes/plugins/paseo-executive/plugin.yaml` is correct
2. Verify the plugin loads without errors
3. Test spawning an agent on local Paseo daemon
4. Test permission request flow
5. Test event delivery
6. Test adding/removing hosts
