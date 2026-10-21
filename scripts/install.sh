#!/bin/sh
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
plugin_destination="${HERMES_HOME:-$HOME/.hermes}/plugins/paseo-executive"
cd "$project_root/bridge"
npm ci --ignore-scripts --no-audit --no-fund
mkdir -p "$(dirname -- "$plugin_destination")"
if [ -e "$plugin_destination" ] || [ -L "$plugin_destination" ]; then
  if [ "$(readlink "$plugin_destination")" != "$project_root" ]; then
    echo "Refusing to overwrite existing plugin at $plugin_destination" >&2
    exit 1
  fi
else
  ln -s "$project_root" "$plugin_destination"
fi
printf 'Installed linked plugin at %s\n' "$plugin_destination"
printf 'Enable with: hermes plugins enable paseo-executive\n'
