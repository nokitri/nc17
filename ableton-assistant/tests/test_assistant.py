import json
import os
import socket
import sys
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "remote_script"), os.path.join(ROOT, "mcp_server"),
                os.path.dirname(os.path.abspath(__file__))]

import fakelive  # noqa: E402
fakelive.install()

from NC17Assistant import quickloop, protocol  # noqa: E402
from NC17Assistant.handlers import Handlers, CommandError  # noqa: E402
from nc17_ableton.client import LiveClient, LiveError  # noqa: E402


class QuickLoopTest(unittest.TestCase):
    NAMES = ["Kick 01.wav", "Snare Tight.wav", "HH Closed.wav", "Perc Conga.wav", "Vox Chop.wav"]

    def test_roles(self):
        self.assertEqual(quickloop.infer_role("909 Kick.wav"), "kick")
        self.assertEqual(quickloop.infer_role("Closed HiHat.aif"), "hat")
        self.assertEqual(quickloop.infer_role("Mystery.wav"), "other")

    def test_deterministic_and_shuffles(self):
        a = quickloop.generate_pattern(self.NAMES, 7, bars=2)
        self.assertEqual(a, quickloop.generate_pattern(self.NAMES, 7, bars=2))
        self.assertNotEqual(a, quickloop.generate_pattern(self.NAMES, 8, bars=2))

    def test_pattern_in_bounds(self):
        notes = quickloop.generate_pattern(self.NAMES, 3, bars=2, density=2.0, swing=0.3)
        self.assertTrue(notes)
        for n in notes:
            self.assertTrue(0 <= n["start_time"] < 8)
            self.assertTrue(36 <= n["pitch"] < 36 + len(self.NAMES))
            self.assertTrue(1 <= n["velocity"] <= 127)

    def test_kick_on_downbeat_mostly(self):
        hits = sum(any(n["pitch"] == 36 and n["start_time"] == 0 for n in
                       quickloop.generate_pattern(["Kick.wav"], s, bars=1)) for s in range(100))
        self.assertGreater(hits, 85)

    def test_pick_prefers_variety(self):
        names = ["Kick A.wav", "Kick B.wav", "Kick C.wav", "Snare.wav", "Hat.wav"]
        picked = quickloop.pick_samples(names, 3, 1)
        self.assertEqual(sorted(quickloop.infer_role(n) for n in picked), ["hat", "kick", "snare"])


class HandlerTest(unittest.TestCase):
    def setUp(self):
        self.surface = fakelive.Surface()
        self.h = Handlers(self.surface)

    def test_session(self):
        s = self.h.dispatch("get_session", {})
        self.assertEqual([t["name"] for t in s["tracks"]], ["Drums", "Bass"])
        self.assertEqual(s["tempo"], 120.0)

    def test_notes_roundtrip_and_replace(self):
        self.h.dispatch("create_clip", {"track": 0, "slot": 0, "length": 4})
        self.h.dispatch("add_notes", {"track": 0, "slot": 0, "notes": [
            {"pitch": 36, "start_time": 0.03, "duration": 0.25, "velocity": 110},
            {"pitch": 38, "start_time": 1.0}]})
        self.h.dispatch("quantize_clip", {"track": 0, "slot": 0, "grid": 0.25})
        notes = self.h.dispatch("get_notes", {"track": 0, "slot": 0})["notes"]
        self.assertEqual([(n["pitch"], n["start_time"]) for n in notes], [(36, 0.0), (38, 1.0)])
        self.h.dispatch("add_notes", {"track": 0, "slot": 0, "replace": True,
                                      "notes": [{"pitch": 60, "start_time": 2}]})
        self.assertEqual(len(self.h.dispatch("get_notes", {"track": 0, "slot": 0})["notes"]), 1)

    def test_errors(self):
        with self.assertRaises(CommandError):
            self.h.dispatch("get_notes", {"track": 9, "slot": 0})
        with self.assertRaises(CommandError):
            self.h.dispatch("nope", {})
        with self.assertRaises(CommandError):
            self.h.dispatch("group_tracks", {"tracks": [0, 1]})

    def test_params_and_mixer(self):
        r = self.h.dispatch("set_parameter", {"track": 0, "device": "auto filter",
                                              "parameter": "Cutoff", "normalized": 2})
        self.assertEqual(r["value"], 20000.0)
        r = self.h.dispatch("set_track", {"track": "return:0", "pan": -3, "volume": 0.5})
        self.assertEqual((r["pan"], r["volume"]), (-1.0, 0.5))

    def test_automation(self):
        self.h.dispatch("create_clip", {"track": 0, "slot": 1, "length": 8})
        self.h.dispatch("set_clip_automation", {"track": 0, "slot": 1, "device": 0,
                        "parameter": "Cutoff", "points": [{"time": 4, "value": 9000}, {"time": 0, "value": 200}]})
        steps = self.surface._song.tracks[0].clip_slots[1].clip.envelopes["Cutoff"].steps
        self.assertEqual(steps, [(0.0, 4.0, 200.0), (4.0, 0.0, 9000.0)])

    def test_arrangement_loops_clips(self):
        self.h.dispatch("create_clip", {"track": 1, "slot": 0, "length": 4})
        r = self.h.dispatch("build_arrangement", {"sections": [{"scene": 0, "bars": 4}, {"scene": 0, "bars": 2}]})
        self.assertEqual(r["end_beat"], 24)
        self.assertEqual([t for t, _ in self.surface._song.tracks[1].arrangement],
                         [0, 4, 8, 12, 16, 20])


class SocketTest(unittest.TestCase):
    """Client <-> protocol round-trip against a stand-in server running Handlers."""

    def test_roundtrip(self):
        h = Handlers(fakelive.Surface())
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def serve():
            conn, _ = srv.accept()
            f = conn.makefile("rb")
            for line in f:
                req = protocol.decode(line)
                try:
                    resp = {"id": req["id"], "ok": True, "result": h.dispatch(req["command"], req["params"])}
                except CommandError as e:
                    resp = {"id": req["id"], "ok": False, "error": str(e)}
                conn.sendall(protocol.encode(resp))

        threading.Thread(target=serve, daemon=True).start()
        c = LiveClient(port=port)
        self.assertEqual(c.call("set_song", tempo=128, loop=None)["tempo"], 128.0)
        with self.assertRaises(LiveError):
            c.call("get_notes", track=0, slot=5)
        c.close()
        srv.close()

    def test_unreachable(self):
        with self.assertRaises(LiveError) as cm:
            LiveClient(port=1).call("ping")
        self.assertIn("Control Surface", str(cm.exception))


class McpServerTest(unittest.TestCase):
    def test_tools_registered(self):
        import asyncio
        from nc17_ableton import server
        names = {t.name for t in asyncio.run(server.mcp.list_tools())}
        for n in ("get_session", "add_notes", "load_item", "quick_loop", "shuffle_loop",
                  "set_clip_automation", "build_arrangement", "mix_snapshot"):
            self.assertIn(n, names)


if __name__ == "__main__":
    unittest.main()
