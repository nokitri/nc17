"""Wire protocol: newline-delimited JSON over TCP on 127.0.0.1.

Request:  {"id": 1, "command": "get_session", "params": {...}}
Response: {"id": 1, "ok": true, "result": ...} or {"id": 1, "ok": false, "error": "..."}
"""
import json

HOST = "127.0.0.1"
PORT = 9877
MAX_LINE = 4 * 1024 * 1024


def encode(obj):
    return (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")


def decode(line):
    return json.loads(line.decode("utf-8"))
