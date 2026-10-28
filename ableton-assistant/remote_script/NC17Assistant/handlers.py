"""Command implementations. Every public `cmd_*` method is a command.

All of these run on Live's main thread. Edits go through the Live API, so
they land in Live's undo history and the Set stays fully editable.
"""
from __future__ import absolute_import

import random

from . import quickloop


class CommandError(Exception):
    pass


BROWSER_CATEGORIES = (
    "instruments", "audio_effects", "midi_effects", "drums", "sounds",
    "samples", "clips", "plugins", "max_for_live", "packs", "user_library",
)
SEARCH_NODE_BUDGET = 30000


def _num(v):
    try:
        return round(float(v), 4)
    except Exception:
        return None


class Handlers(object):
    def __init__(self, surface):
        self._surface = surface
        self._uri_cache = {}
        self._loops = {}  # track name -> quick-loop state for shuffle

    # -- plumbing --------------------------------------------------------
    @property
    def song(self):
        return self._surface.song()

    @property
    def app(self):
        import Live
        return Live.Application.get_application()

    def dispatch(self, command, params):
        fn = getattr(self, "cmd_" + str(command), None)
        if fn is None:
            raise CommandError("unknown command: %s" % command)
        return fn(**params)

    def _track(self, track):
        """track: int index, 'master', or 'return:N'."""
        s = self.song
        if track == "master":
            return s.master_track
        if isinstance(track, str) and track.startswith("return:"):
            idx = int(track.split(":", 1)[1])
            if not 0 <= idx < len(s.return_tracks):
                raise CommandError("no return track %d" % idx)
            return s.return_tracks[idx]
        try:
            idx = int(track)
        except (TypeError, ValueError):
            raise CommandError("bad track reference: %r" % (track,))
        if not 0 <= idx < len(s.tracks):
            raise CommandError("track index %d out of range (0-%d)" % (idx, len(s.tracks) - 1))
        return s.tracks[idx]

    def _slot(self, track, slot):
        t = self._track(track)
        if not 0 <= int(slot) < len(t.clip_slots):
            raise CommandError("clip slot %s out of range" % slot)
        return t.clip_slots[int(slot)]

    def _clip(self, track, slot):
        cs = self._slot(track, slot)
        if not cs.has_clip:
            raise CommandError("no clip at track %s slot %s" % (track, slot))
        return cs.clip

    def _device(self, track, device):
        t = self._track(track)
        devs = list(t.devices)
        if isinstance(device, int) or (isinstance(device, str) and device.isdigit()):
            i = int(device)
            if not 0 <= i < len(devs):
                raise CommandError("device index %d out of range" % i)
            return devs[i]
        for d in devs:
            if d.name.lower() == str(device).lower():
                return d
        raise CommandError("no device named %r on track" % device)

    def _param(self, device, parameter):
        params = list(device.parameters)
        if isinstance(parameter, int) or (isinstance(parameter, str) and parameter.isdigit()):
            i = int(parameter)
            if not 0 <= i < len(params):
                raise CommandError("parameter index %d out of range" % i)
            return params[i]
        for p in params:
            if p.name.lower() == str(parameter).lower():
                return p
        raise CommandError("no parameter %r on %s" % (parameter, device.name))

    def _track_summary(self, t, index=None):
        info = {"name": t.name}
        if index is not None:
            info["index"] = index
        md = t.mixer_device
        info["volume"] = _num(md.volume.value)
        info["volume_db"] = md.volume.str_for_value(md.volume.value)
        info["pan"] = _num(md.panning.value)
        for attr in ("mute", "solo", "arm", "has_midi_input", "has_audio_input", "is_foldable", "is_grouped"):
            if hasattr(t, attr):
                try:
                    info[attr] = bool(getattr(t, attr))
                except Exception:
                    pass
        if hasattr(t, "color_index"):
            info["color_index"] = t.color_index
        info["devices"] = [d.name for d in t.devices]
        if hasattr(t, "output_meter_level"):
            info["meter"] = _num(t.output_meter_level)
        return info

    # -- session -----------------------------------------------------------
    def cmd_ping(self):
        return {"live_version": "%d.%d.%d" % (self.app.get_major_version(),
                                             self.app.get_minor_version(),
                                             self.app.get_bugfix_version())}

    def cmd_get_session(self):
        s = self.song
        tracks = []
        for i, t in enumerate(s.tracks):
            info = self._track_summary(t, i)
            info["clips"] = [
                {"slot": j, "name": cs.clip.name, "length": cs.clip.length,
                 "is_midi": cs.clip.is_midi_clip}
                for j, cs in enumerate(t.clip_slots) if cs.has_clip
            ]
            tracks.append(info)
        return {
            "tempo": s.tempo,
            "time_signature": [s.signature_numerator, s.signature_denominator],
            "is_playing": s.is_playing,
            "loop": {"start": s.loop_start, "length": s.loop_length, "on": s.loop},
            "song_length": s.song_length,
            "scenes": [{"index": i, "name": sc.name} for i, sc in enumerate(s.scenes)],
            "tracks": tracks,
            "return_tracks": [self._track_summary(t, i) for i, t in enumerate(s.return_tracks)],
            "master": self._track_summary(s.master_track),
        }

    def cmd_set_song(self, tempo=None, numerator=None, denominator=None,
                     loop_start=None, loop_length=None, loop=None, metronome=None):
        s = self.song
        if tempo is not None:
            s.tempo = float(tempo)
        if numerator is not None:
            s.signature_numerator = int(numerator)
        if denominator is not None:
            s.signature_denominator = int(denominator)
        if loop_start is not None:
            s.loop_start = float(loop_start)
        if loop_length is not None:
            s.loop_length = float(loop_length)
        if loop is not None:
            s.loop = bool(loop)
        if metronome is not None:
            s.metronome = bool(metronome)
        return {"tempo": s.tempo}

    def cmd_transport(self, action):
        s = self.song
        if action == "play":
            s.start_playing()
        elif action == "stop":
            s.stop_playing()
        elif action == "continue":
            s.continue_playing()
        elif action == "stop_all_clips":
            s.stop_all_clips()
        elif action == "undo":
            if s.can_undo:
                s.undo()
        elif action == "redo":
            if s.can_redo:
                s.redo()
        else:
            raise CommandError("unknown transport action %r" % action)
        return {"is_playing": s.is_playing}

    # -- tracks ------------------------------------------------------------
    def cmd_create_track(self, kind="midi", index=-1, name=None, color_index=None):
        s = self.song
        if kind == "midi":
            s.create_midi_track(int(index))
        elif kind == "audio":
            s.create_audio_track(int(index))
        elif kind == "return":
            s.create_return_track()
            t = s.return_tracks[-1]
            if name:
                t.name = name
            return {"track": "return:%d" % (len(s.return_tracks) - 1)}
        else:
            raise CommandError("kind must be midi, audio or return")
        new_index = len(s.tracks) - 1 if int(index) < 0 else int(index)
        t = s.tracks[new_index]
        if name:
            t.name = name
        if color_index is not None:
            t.color_index = int(color_index)
        return {"track": new_index, "name": t.name}

    def cmd_delete_track(self, track):
        s = self.song
        if isinstance(track, str) and track.startswith("return:"):
            s.delete_return_track(int(track.split(":")[1]))
        else:
            s.delete_track(int(track))
        return {"deleted": track}

    def cmd_duplicate_track(self, track):
        self.song.duplicate_track(int(track))
        return {"track": int(track) + 1}

    def cmd_set_track(self, track, name=None, mute=None, solo=None, arm=None,
                      volume=None, pan=None, sends=None, color_index=None):
        t = self._track(track)
        md = t.mixer_device
        if name is not None:
            t.name = name
        if mute is not None:
            t.mute = bool(mute)
        if solo is not None:
            t.solo = bool(solo)
        if arm is not None and t.can_be_armed:
            t.arm = bool(arm)
        if volume is not None:
            md.volume.value = max(md.volume.min, min(md.volume.max, float(volume)))
        if pan is not None:
            md.panning.value = max(-1.0, min(1.0, float(pan)))
        if sends:
            for i, v in enumerate(sends):
                if v is not None and i < len(md.sends):
                    md.sends[i].value = max(0.0, min(1.0, float(v)))
        if color_index is not None:
            t.color_index = int(color_index)
        return self._track_summary(t)

    def cmd_group_tracks(self, tracks, name=None):
        # Live's API has no stable group-creation call; use it only where present.
        s = self.song
        fn = getattr(s, "create_group_track", None)
        if fn is None:
            raise CommandError(
                "This Live version does not expose track grouping to scripts. "
                "Select the tracks and press Cmd/Ctrl+G in Live.")
        group = fn([self._track(i) for i in tracks])
        if name and group is not None:
            group.name = name
        return {"grouped": tracks}

    # -- clips & notes -----------------------------------------------------
    def cmd_create_clip(self, track, slot, length=4.0, name=None):
        cs = self._slot(track, slot)
        if cs.has_clip:
            raise CommandError("slot already has a clip; delete it first")
        cs.create_clip(float(length))
        if name:
            cs.clip.name = name
        return {"track": track, "slot": slot, "length": cs.clip.length}

    def cmd_delete_clip(self, track, slot):
        self._slot(track, slot).delete_clip()
        return {"deleted": [track, slot]}

    def cmd_duplicate_clip(self, track, slot, target_slot):
        self._slot(track, slot).duplicate_clip_to(self._slot(track, target_slot))
        return {"track": track, "slot": target_slot}

    def cmd_set_clip(self, track, slot, name=None, loop_start=None, loop_end=None,
                     looping=None, color_index=None, gain=None, pitch_coarse=None, warping=None):
        c = self._clip(track, slot)
        if name is not None:
            c.name = name
        if loop_end is not None:
            c.loop_end = float(loop_end)
        if loop_start is not None:
            c.loop_start = float(loop_start)
        if looping is not None:
            c.looping = bool(looping)
        if color_index is not None:
            c.color_index = int(color_index)
        if c.is_audio_clip:
            if gain is not None:
                c.gain = float(gain)
            if pitch_coarse is not None:
                c.pitch_coarse = int(pitch_coarse)
            if warping is not None:
                c.warping = bool(warping)
        return {"name": c.name, "length": c.length, "loop_start": c.loop_start, "loop_end": c.loop_end}

    def cmd_get_notes(self, track, slot):
        c = self._clip(track, slot)
        if not c.is_midi_clip:
            raise CommandError("not a MIDI clip")
        notes = c.get_notes_extended(0, 128, 0.0, max(c.length, c.loop_end))
        return {"length": c.length, "notes": [
            {"pitch": n.pitch, "start_time": _num(n.start_time), "duration": _num(n.duration),
             "velocity": _num(n.velocity), "mute": n.mute}
            for n in notes]}

    def _note_specs(self, notes):
        import Live
        specs = []
        for n in notes:
            specs.append(Live.Clip.MidiNoteSpecification(
                pitch=int(n["pitch"]),
                start_time=float(n["start_time"]),
                duration=max(0.001, float(n.get("duration", 0.25))),
                velocity=float(n.get("velocity", 100)),
                mute=bool(n.get("mute", False)),
            ))
        return tuple(specs)

    def cmd_add_notes(self, track, slot, notes, replace=False):
        c = self._clip(track, slot)
        if not c.is_midi_clip:
            raise CommandError("not a MIDI clip")
        if replace:
            c.remove_notes_extended(0, 128, 0.0, max(c.length, c.loop_end) + 1)
        if notes:
            c.add_new_notes(self._note_specs(notes))
        return {"added": len(notes), "replaced": bool(replace)}

    def cmd_remove_notes(self, track, slot, from_pitch=0, pitch_span=128, from_time=0.0, time_span=None):
        c = self._clip(track, slot)
        span = float(time_span) if time_span is not None else max(c.length, c.loop_end) + 1
        c.remove_notes_extended(int(from_pitch), int(pitch_span), float(from_time), span)
        return {"ok": True}

    def cmd_quantize_clip(self, track, slot, grid=0.25, amount=1.0):
        c = self._clip(track, slot)
        # Live's quantize takes a RecordingQuantization enum; do it on notes for any grid.
        notes = self.cmd_get_notes(track, slot)["notes"]
        g = float(grid)
        for n in notes:
            target = round(n["start_time"] / g) * g
            n["start_time"] = n["start_time"] + (target - n["start_time"]) * float(amount)
        self.cmd_add_notes(track, slot, notes, replace=True)
        return {"quantized": len(notes), "grid": g}

    def cmd_fire(self, track=None, slot=None, scene=None):
        if scene is not None:
            self.song.scenes[int(scene)].fire()
        else:
            self._slot(track, slot).fire()
        return {"ok": True}

    def cmd_stop_track(self, track):
        self._track(track).stop_all_clips()
        return {"ok": True}

    # -- scenes & arrangement ----------------------------------------------
    def cmd_create_scene(self, index=-1, name=None):
        s = self.song
        s.create_scene(int(index))
        i = len(s.scenes) - 1 if int(index) < 0 else int(index)
        if name:
            s.scenes[i].name = name
        return {"scene": i}

    def cmd_set_scene(self, scene, name=None, tempo=None):
        sc = self.song.scenes[int(scene)]
        if name is not None:
            sc.name = name
        if tempo is not None and hasattr(sc, "tempo"):
            sc.tempo = float(tempo)
        return {"scene": scene, "name": sc.name}

    def cmd_duplicate_scene(self, scene):
        self.song.duplicate_scene(int(scene))
        return {"scene": int(scene) + 1}

    def cmd_build_arrangement(self, sections, start_bar=1):
        """sections: [{"scene": i, "bars": n, "mute_tracks": [..]}]. Copies each
        scene's clips into the Arrangement back to back (Live 11+)."""
        s = self.song
        beats_per_bar = 4.0 * s.signature_numerator / s.signature_denominator
        time = (int(start_bar) - 1) * beats_per_bar
        placed = []
        for sec in sections:
            scene = int(sec["scene"])
            bars = float(sec.get("bars", 8))
            skip = set(int(t) for t in sec.get("mute_tracks", []))
            section_len = bars * beats_per_bar
            for ti, t in enumerate(s.tracks):
                if ti in skip or scene >= len(t.clip_slots):
                    continue
                cs = t.clip_slots[scene]
                if not cs.has_clip:
                    continue
                if not hasattr(t, "duplicate_clip_to_arrangement"):
                    raise CommandError("Arrangement editing needs Live 11 or later")
                clip_len = cs.clip.length
                pos = 0.0
                while pos < section_len - 1e-6:
                    t.duplicate_clip_to_arrangement(cs.clip, time + pos)
                    pos += clip_len
                placed.append({"track": ti, "scene": scene, "at_beat": time})
            time += section_len
        return {"clips_placed": len(placed), "end_beat": time,
                "note": "Clips that overrun a section end can be trimmed in Live."}

    # -- devices -----------------------------------------------------------
    def cmd_get_devices(self, track):
        t = self._track(track)
        out = []
        for i, d in enumerate(t.devices):
            info = {"index": i, "name": d.name, "class_name": d.class_name,
                    "type": str(d.type), "is_active": d.is_active,
                    "parameter_count": len(d.parameters)}
            if d.can_have_chains:
                info["chains"] = [c.name for c in d.chains]
            out.append(info)
        return out

    def cmd_get_parameters(self, track, device):
        d = self._device(track, device)
        return {"device": d.name, "parameters": [
            {"index": i, "name": p.name, "value": _num(p.value), "min": _num(p.min),
             "max": _num(p.max), "display": p.str_for_value(p.value), "quantized": p.is_quantized,
             "enabled": p.is_enabled}
            for i, p in enumerate(d.parameters)]}

    def cmd_set_parameter(self, track, device, parameter, value=None, normalized=None):
        d = self._device(track, device)
        p = self._param(d, parameter)
        if normalized is not None:
            value = p.min + (p.max - p.min) * max(0.0, min(1.0, float(normalized)))
        if value is None:
            raise CommandError("give value or normalized")
        p.value = max(p.min, min(p.max, float(value)))
        return {"name": p.name, "value": _num(p.value), "display": p.str_for_value(p.value)}

    def cmd_toggle_device(self, track, device, on=True):
        d = self._device(track, device)
        self._param(d, 0).value = 1.0 if on else 0.0  # parameter 0 is "Device On"
        return {"device": d.name, "on": bool(on)}

    def cmd_delete_device(self, track, device):
        t = self._track(track)
        d = self._device(track, device)
        t.delete_device(list(t.devices).index(d))
        return {"deleted": d.name}

    # -- automation (clip envelopes) -----------------------------------------
    def cmd_set_clip_automation(self, track, slot, device, parameter, points, clear=True):
        """points: [{"time": beats, "value": v, "duration": beats?}] in parameter units.
        device may be 'mixer' with parameter 'volume'/'pan'/'send:N'."""
        c = self._clip(track, slot)
        if device == "mixer":
            md = self._track(track).mixer_device
            if parameter == "volume":
                p = md.volume
            elif parameter == "pan":
                p = md.panning
            elif str(parameter).startswith("send:"):
                p = md.sends[int(str(parameter).split(":")[1])]
            else:
                raise CommandError("mixer parameter must be volume, pan or send:N")
        else:
            p = self._param(self._device(track, device), parameter)
        env = c.automation_envelope(p)
        if env is not None and clear:
            c.clear_envelope(p)
            env = None
        if env is None:
            env = c.create_automation_envelope(p)
        if env is None:
            raise CommandError("Live does not allow automation of %s here" % p.name)
        pts = sorted(points, key=lambda x: float(x["time"]))
        for i, pt in enumerate(pts):
            t0 = float(pt["time"])
            dur = pt.get("duration")
            if dur is None:
                dur = (float(pts[i + 1]["time"]) - t0) if i + 1 < len(pts) else 0.0
            v = max(p.min, min(p.max, float(pt["value"])))
            env.insert_step(t0, float(dur), v)
        return {"parameter": p.name, "points": len(pts)}

    def cmd_clear_clip_automation(self, track, slot):
        self._clip(track, slot).clear_all_envelopes()
        return {"ok": True}

    # -- browser / loading -----------------------------------------------------
    def _roots(self, category=None):
        b = self.app.browser
        if category in (None, "all"):
            cats = BROWSER_CATEGORIES
        else:
            cats = (category,)
        roots = []
        for c in cats:
            if c == "user_folders":
                continue
            node = getattr(b, c, None)
            if node is not None:
                roots.append((c, node))
        if category in (None, "all", "user_folders"):
            for f in getattr(b, "user_folders", []):
                roots.append(("user_folders", f))
        if not roots:
            raise CommandError("unknown browser category %r" % category)
        return roots

    def _item_info(self, item, path):
        self._uri_cache[item.uri] = item
        return {"name": item.name, "uri": item.uri, "path": path,
                "loadable": item.is_loadable, "folder": item.is_folder}

    def cmd_browse(self, category, path=""):
        roots = self._roots(category)
        node = roots[0][1]
        if category == "user_folders":
            parts = [p for p in path.split("/") if p]
            if not parts:
                return [self._item_info(r, r.name) for _, r in roots]
            node = next((r for _, r in roots if r.name == parts[0]), None)
            if node is None:
                raise CommandError("no user folder %r" % parts[0])
            parts = parts[1:]
        else:
            parts = [p for p in path.split("/") if p]
        walked = []
        for part in parts:
            nxt = next((ch for ch in node.children if ch.name == part), None)
            if nxt is None:
                raise CommandError("%r not found under %r" % (part, "/".join(walked) or category))
            node = nxt
            walked.append(part)
        base = "/".join(([] if category != "user_folders" else [path.split("/")[0]]) + walked)
        return [self._item_info(ch, (base + "/" if base else "") + ch.name) for ch in node.children]

    def _walk(self, roots, predicate, limit):
        found, visited = [], 0
        stack = [(node, cat + ":" + getattr(node, "name", "")) for cat, node in roots]
        while stack and len(found) < limit and visited < SEARCH_NODE_BUDGET:
            node, path = stack.pop()
            visited += 1
            for ch in node.children:
                p = path + "/" + ch.name
                if ch.is_loadable and predicate(ch, p):
                    found.append(self._item_info(ch, p))
                    if len(found) >= limit:
                        break
                if ch.is_folder or ch.children:
                    stack.append((ch, p))
        return found, visited

    def cmd_search_browser(self, query, category=None, limit=25):
        words = [w for w in str(query).lower().split() if w]
        found, visited = self._walk(
            self._roots(category),
            lambda it, p: all(w in it.name.lower() for w in words),
            int(limit))
        return {"results": found, "searched_nodes": visited,
                "truncated": visited >= SEARCH_NODE_BUDGET}

    def _find_uri(self, uri):
        item = self._uri_cache.get(uri)
        if item is not None:
            return item
        found, _ = self._walk(self._roots(None), lambda it, p: it.uri == uri, 1)
        if not found:
            raise CommandError("browser item not found; search for it first")
        return self._uri_cache[uri]

    def cmd_load_item(self, uri, track, slot=None):
        """Load an instrument, effect, preset, plugin or sample onto a track.
        Samples on an audio track with `slot` go into that clip slot."""
        t = self._track(track)
        item = self._find_uri(uri)
        self.song.view.selected_track = t
        if slot is not None:
            self.song.view.highlighted_clip_slot = t.clip_slots[int(slot)]
        self.app.browser.load_item(item)
        return {"loaded": item.name, "track": track, "devices": [d.name for d in t.devices]}

    # -- mixing ------------------------------------------------------------------
    def cmd_mix_snapshot(self):
        """Gain-staging view: meters (only meaningful while playing), volumes, sends, devices."""
        s = self.song
        rows = [self._track_summary(t, i) for i, t in enumerate(s.tracks)]
        for row, t in zip(rows, s.tracks):
            row["sends"] = [_num(x.value) for x in t.mixer_device.sends]
        return {"is_playing": s.is_playing, "tracks": rows,
                "returns": [self._track_summary(t, i) for i, t in enumerate(s.return_tracks)],
                "master": self._track_summary(s.master_track)}

    # -- Quick Loop + Shuffle ------------------------------------------------------
    def _drum_rack(self, track):
        for d in track.devices:
            if d.can_have_drum_pads:
                return d
        return None

    def cmd_quick_loop(self, folder_query, track_name="Quick Loop", pads=6, bars=2,
                       density=1.0, swing=0.0, seed=None, category="user_folders"):
        """Build a drum-rack loop from samples whose path matches folder_query."""
        words = [w for w in str(folder_query).lower().split() if w]
        samples, _ = self._walk(
            self._roots(category),
            lambda it, p: not it.is_folder and it.name.lower().endswith(
                (".wav", ".aif", ".aiff", ".flac", ".mp3", ".ogg"))
            and all(w in p.lower() for w in words),
            2000)
        if not samples:
            raise CommandError("no samples matched %r in %s" % (folder_query, category))
        seed = int(seed) if seed is not None else random.randint(0, 2 ** 31 - 1)
        by_name = dict((x["name"], x) for x in samples)
        names = quickloop.pick_samples(list(by_name), int(pads), seed)

        s = self.song
        s.create_midi_track(-1)
        ti = len(s.tracks) - 1
        t = s.tracks[ti]
        t.name = track_name
        rack_item = self._walk(self._roots("instruments"), lambda it, p: it.name == "Drum Rack", 1)[0]
        if not rack_item:
            raise CommandError("could not find the stock Drum Rack in the browser")
        s.view.selected_track = t
        self.app.browser.load_item(self._uri_cache[rack_item[0]["uri"]])
        rack = self._drum_rack(t)
        if rack is None:
            raise CommandError("Drum Rack did not load")
        for i, name in enumerate(names):
            rack.view.selected_drum_pad = rack.drum_pads[quickloop.FIRST_PAD + i]
            self.app.browser.load_item(self._uri_cache[by_name[name]["uri"]])

        self._loops[ti] = {"names": names, "bars": int(bars), "density": float(density),
                           "swing": float(swing), "pool": list(by_name)}
        result = self._write_loop(ti, seed)
        result.update({"track": ti, "samples": names})
        return result

    def _write_loop(self, ti, seed):
        st = self._loops[ti]
        s = self.song
        beats_per_bar = 4.0 * s.signature_numerator / s.signature_denominator
        cs = s.tracks[ti].clip_slots[0]
        if cs.has_clip:
            cs.delete_clip()
        cs.create_clip(st["bars"] * beats_per_bar)
        cs.clip.name = "Loop %d" % seed
        notes = quickloop.generate_pattern(st["names"], seed, st["bars"], st["density"],
                                           st["swing"], int(beats_per_bar))
        if notes:
            cs.clip.add_new_notes(self._note_specs(notes))
        return {"seed": seed, "notes": len(notes)}

    def cmd_shuffle_loop(self, track, seed=None, density=None, swing=None):
        """Re-roll a Quick Loop's pattern (same samples). Keep the seed to recall it."""
        ti = int(track)
        if ti not in self._loops:
            raise CommandError("track %d is not a Quick Loop from this session" % ti)
        st = self._loops[ti]
        if density is not None:
            st["density"] = float(density)
        if swing is not None:
            st["swing"] = float(swing)
        seed = int(seed) if seed is not None else random.randint(0, 2 ** 31 - 1)
        return self._write_loop(ti, seed)
