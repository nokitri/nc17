"""Minimal stand-ins for Live's Python API, enough to drive Handlers in tests."""
import sys
import types


class Param:
    def __init__(self, name, value=0.0, lo=0.0, hi=1.0):
        self.name, self.value, self.min, self.max = name, value, lo, hi
        self.is_quantized, self.is_enabled = False, True

    def str_for_value(self, v):
        return "%.2f" % v


class Note:
    def __init__(self, spec):
        self.__dict__.update(spec.__dict__)


class Clip:
    def __init__(self, length):
        self.length, self.loop_start, self.loop_end = length, 0.0, length
        self.name, self.is_midi_clip, self.is_audio_clip = "", True, False
        self.notes, self.envelopes = [], {}

    def add_new_notes(self, specs):
        self.notes += [Note(s) for s in specs]

    def get_notes_extended(self, p, ps, t, ts):
        return [n for n in self.notes if p <= n.pitch < p + ps and t <= n.start_time < t + ts]

    def remove_notes_extended(self, p, ps, t, ts):
        drop = self.get_notes_extended(p, ps, t, ts)
        self.notes = [n for n in self.notes if n not in drop]

    def automation_envelope(self, p):
        return self.envelopes.get(p.name)

    def create_automation_envelope(self, p):
        self.envelopes[p.name] = Envelope()
        return self.envelopes[p.name]

    def clear_envelope(self, p):
        self.envelopes.pop(p.name, None)


class Envelope:
    def __init__(self):
        self.steps = []

    def insert_step(self, t, d, v):
        self.steps.append((t, d, v))


class Slot:
    def __init__(self):
        self.clip = None

    @property
    def has_clip(self):
        return self.clip is not None

    def create_clip(self, length):
        self.clip = Clip(length)

    def delete_clip(self):
        self.clip = None


class Mixer:
    def __init__(self):
        self.volume = Param("Volume", 0.85)
        self.panning = Param("Pan", 0.0, -1.0, 1.0)
        self.sends = [Param("Send A")]


class Device:
    def __init__(self, name):
        self.name = self.class_name = name
        self.type, self.is_active, self.can_have_chains, self.can_have_drum_pads = 1, True, False, False
        self.parameters = [Param("Device On", 1.0), Param("Cutoff", 500.0, 20.0, 20000.0)]


class Track:
    def __init__(self, name):
        self.name, self.mute, self.solo, self.arm, self.can_be_armed = name, False, False, False, True
        self.color_index, self.has_midi_input = 0, True
        self.mixer_device = Mixer()
        self.devices = [Device("Auto Filter")]
        self.clip_slots = [Slot() for _ in range(8)]
        self.arrangement = []

    def duplicate_clip_to_arrangement(self, clip, t):
        self.arrangement.append((t, clip.length))


class Song:
    def __init__(self):
        self.tempo, self.signature_numerator, self.signature_denominator = 120.0, 4, 4
        self.is_playing, self.loop, self.loop_start, self.loop_length, self.song_length = False, False, 0, 16, 0
        self.tracks = [Track("Drums"), Track("Bass")]
        self.return_tracks = [Track("Reverb")]
        self.master_track = Track("Master")
        self.scenes = []

    def create_midi_track(self, i):
        t = Track("MIDI")
        self.tracks.insert(len(self.tracks) if i < 0 else i, t)


class Surface:
    def __init__(self):
        self._song = Song()

    def song(self):
        return self._song


def install():
    live = types.ModuleType("Live")
    clip_mod = types.ModuleType("Live.Clip")

    class MidiNoteSpecification:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    clip_mod.MidiNoteSpecification = MidiNoteSpecification
    live.Clip = clip_mod
    sys.modules["Live"] = live
    sys.modules["Live.Clip"] = clip_mod
