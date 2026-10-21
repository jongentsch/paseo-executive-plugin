# Build a Paseo Plugin

## Goal
Create a Paseo plugin that makes Hermes an executive assistant for managing Paseo coding workers across multiple daemon hosts.

## What It Needs to Do
- Manage multiple Paseo daemon hosts (local, remote, SSH)
- Spawn agents on those hosts
- Surface permission requests from agents for user approval
- Subscribe to agent events (completions, failures, permissions)
- Deliver those events back to Hermes for notification

## Requirements
- Build as a Paseo plugin (standard plugin structure)
- Deploy to `~/.hermes/plugins/`
- This is a new project — create a new repo for it
- Use whatever tech stack and naming conventions make sense for Paseo plugins

## Context
- Paseo CLI: `/Applications/Paseo.app/Contents/Resources/bin/paseo`
- Hermes plugin system at `~/.hermes/plugins/`
- User wants an executive layer, not a coding tool
- Agents should work asynchronously and relay events back
