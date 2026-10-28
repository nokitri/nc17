from __future__ import absolute_import

import socket
import threading
import traceback

try:
    import queue
except ImportError:  # pragma: no cover
    import Queue as queue

from _Framework.ControlSurface import ControlSurface

from . import protocol
from .handlers import Handlers, CommandError


class _Pending(object):
    def __init__(self, request):
        self.request = request
        self.response = None
        self.done = threading.Event()


class NC17Assistant(ControlSurface):
    """Accepts commands on a background socket thread and runs them on
    Live's main thread (drained from update_display, ~10x per second),
    because the Live API is not thread-safe."""

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._queue = queue.Queue()
        self._running = True
        self._handlers = Handlers(self)
        self._server = None
        self._thread = threading.Thread(target=self._serve, name="NC17Assistant")
        self._thread.daemon = True
        self._thread.start()
        self.log_message("NC17 Assistant listening on %s:%d" % (protocol.HOST, protocol.PORT))
        self.show_message("NC17 Assistant ready")

    # -- main thread ---------------------------------------------------
    def update_display(self):
        ControlSurface.update_display(self)
        while True:
            try:
                pending = self._queue.get_nowait()
            except queue.Empty:
                break
            pending.response = self._execute(pending.request)
            pending.done.set()

    def _execute(self, request):
        rid = request.get("id")
        try:
            result = self._handlers.dispatch(request.get("command"), request.get("params") or {})
            return {"id": rid, "ok": True, "result": result}
        except CommandError as e:
            return {"id": rid, "ok": False, "error": str(e)}
        except Exception as e:
            self.log_message("NC17 error: " + traceback.format_exc())
            return {"id": rid, "ok": False, "error": "%s: %s" % (type(e).__name__, e)}

    def disconnect(self):
        self._running = False
        if self._server is not None:
            try:
                self._server.close()
            except Exception:
                pass
        ControlSurface.disconnect(self)

    # -- socket thread -------------------------------------------------
    def _serve(self):
        try:
            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.bind((protocol.HOST, protocol.PORT))
            self._server.listen(4)
            self._server.settimeout(1.0)
        except Exception as e:
            self.log_message("NC17 could not open socket: %s" % e)
            return
        while self._running:
            try:
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            t = threading.Thread(target=self._client, args=(conn,))
            t.daemon = True
            t.start()

    def _client(self, conn):
        conn.settimeout(None)
        buf = b""
        try:
            while self._running:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > protocol.MAX_LINE:
                    break
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        request = protocol.decode(line)
                    except ValueError as e:
                        conn.sendall(protocol.encode({"id": None, "ok": False, "error": "bad json: %s" % e}))
                        continue
                    pending = _Pending(request)
                    self._queue.put(pending)
                    if not pending.done.wait(30.0):
                        resp = {"id": request.get("id"), "ok": False, "error": "timed out waiting for Live"}
                    else:
                        resp = pending.response
                    conn.sendall(protocol.encode(resp))
        except Exception as e:
            self.log_message("NC17 client error: %s" % e)
        finally:
            try:
                conn.close()
            except Exception:
                pass
