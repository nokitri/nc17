"""Socket client for the NC17Assistant Remote Script running inside Live."""
import itertools
import json
import os
import socket
import threading

HOST = os.environ.get("NC17_HOST", "127.0.0.1")
PORT = int(os.environ.get("NC17_PORT", "9877"))


class LiveError(RuntimeError):
    pass


class LiveClient:
    def __init__(self, host=HOST, port=PORT, timeout=35.0):
        self.host, self.port, self.timeout = host, port, timeout
        self._sock = None
        self._file = None
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def _connect(self):
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as e:
            raise LiveError(
                "Can't reach Ableton Live on %s:%d (%s). Open Live 12 and pick 'NC17Assistant' "
                "as a Control Surface in Settings > Link, Tempo & MIDI." % (self.host, self.port, e))
        self._file = self._sock.makefile("rb")

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = self._file = None

    def call(self, command, **params):
        params = {k: v for k, v in params.items() if v is not None}
        with self._lock:
            # Retry once only if the *send* fails (stale socket), never after Live
            # may have run the command, so edits are never applied twice.
            for attempt in (0, 1):
                if self._sock is None:
                    self._connect()
                rid = next(self._ids)
                payload = json.dumps({"id": rid, "command": command, "params": params}) + "\n"
                try:
                    self._sock.sendall(payload.encode())
                    break
                except OSError:
                    self.close()
                    if attempt:
                        raise LiveError("Lost connection to Ableton Live")
            try:
                line = self._file.readline()
            except OSError as e:
                self.close()
                raise LiveError("No reply from Ableton Live (%s)" % e)
            if not line:
                self.close()
                raise LiveError("Live closed the connection")
            resp = json.loads(line)
        if not resp.get("ok"):
            raise LiveError(resp.get("error", "unknown error"))
        return resp.get("result")
