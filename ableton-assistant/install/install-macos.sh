#!/usr/bin/env bash
# Installs NC17 Assistant for Ableton Live 12 on macOS and registers it with
# Claude Code and/or Codex if their CLIs are installed.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="${NC17_REMOTE_SCRIPTS:-$HOME/Music/Ableton/User Library/Remote Scripts}"
VENV="$HOME/.nc17-ableton"

echo "-> Remote Script -> $SCRIPTS/NC17Assistant"
mkdir -p "$SCRIPTS"
rm -rf "$SCRIPTS/NC17Assistant"
cp -R "$HERE/remote_script/NC17Assistant" "$SCRIPTS/"

echo "-> MCP server -> $VENV"
PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo "python3 (3.10+) is required: https://www.python.org/downloads/"; exit 1; }
"$PY" -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q "$HERE/mcp_server"
BIN="$VENV/bin/nc17-ableton"

if command -v claude >/dev/null; then
  claude mcp remove nc17-ableton -s user >/dev/null 2>&1 || true
  claude mcp add nc17-ableton -s user -- "$BIN" && echo "-> Registered with Claude Code"
fi
if command -v codex >/dev/null; then
  codex mcp remove nc17-ableton >/dev/null 2>&1 || true
  codex mcp add nc17-ableton -- "$BIN" && echo "-> Registered with Codex"
fi

cat <<MSG

Done. In Live 12: Settings > Link, Tempo & MIDI > Control Surface -> NC17Assistant
(restart Live if it is not listed). MCP server command: $BIN
MSG
