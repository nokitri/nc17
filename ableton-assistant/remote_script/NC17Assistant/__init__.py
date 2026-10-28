"""NC17 Assistant - Ableton Live 12 Remote Script.

Exposes the open Live Set over a local-only JSON socket so the NC17 MCP
server (used by Claude Code or Codex) can read and edit it.
"""
from __future__ import absolute_import


def create_instance(c_instance):
    from .assistant import NC17Assistant
    return NC17Assistant(c_instance)
