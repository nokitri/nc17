"""NC17 Ableton MCP server: tools Claude Code / Codex use to work in Live.

Tracks are addressed by index (0-based), "master", or "return:N".
Times are in beats (quarter notes); bar 1 starts at beat 0.
"""
import json
from typing import Any, Optional, Union

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as FastMCP
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP
    from mcp.server.fastmcp.exceptions import ToolError

from .client import LiveClient, LiveError

INSTRUCTIONS = """You are a music production assistant working inside the user's open
Ableton Live 12 set. Always call get_session first to learn the tracks, clips and tempo.
Prefer small, reversible edits; everything you do is in Live's undo history (transport
action 'undo'). Before loading plugins or samples, find them with search_browser or browse;
use the user's own sample folders (category 'user_folders') when they mention their packs.
Read device parameters before changing them and report values in their display units.
Meters in mix_snapshot are only meaningful while the transport is playing."""

mcp = FastMCP("nc17-ableton", instructions=INSTRUCTIONS)
live = LiveClient()

Track = Union[int, str]


def _call(command: str, **params: Any) -> str:
    try:
        return json.dumps(live.call(command, **params), indent=1)
    except LiveError as e:
        raise ToolError(str(e))


# -- session & transport ------------------------------------------------------
@mcp.tool()
def get_session() -> str:
    """Overview of the open set: tempo, time signature, scenes, every track with
    its clips, devices, volume and pan, plus returns and master."""
    return _call("get_session")


@mcp.tool()
def set_song(tempo: Optional[float] = None, numerator: Optional[int] = None,
             denominator: Optional[int] = None, loop_start: Optional[float] = None,
             loop_length: Optional[float] = None, loop: Optional[bool] = None,
             metronome: Optional[bool] = None) -> str:
    """Set song tempo, time signature, arrangement loop (beats) or metronome."""
    return _call("set_song", tempo=tempo, numerator=numerator, denominator=denominator,
                 loop_start=loop_start, loop_length=loop_length, loop=loop, metronome=metronome)


@mcp.tool()
def transport(action: str) -> str:
    """action: play | stop | continue | stop_all_clips | undo | redo."""
    return _call("transport", action=action)


# -- tracks ---------------------------------------------------------------------
@mcp.tool()
def create_track(kind: str = "midi", index: int = -1, name: Optional[str] = None,
                 color_index: Optional[int] = None) -> str:
    """Create a 'midi', 'audio' or 'return' track. index -1 appends."""
    return _call("create_track", kind=kind, index=index, name=name, color_index=color_index)


@mcp.tool()
def delete_track(track: Track) -> str:
    """Delete a track (index or 'return:N')."""
    return _call("delete_track", track=track)


@mcp.tool()
def duplicate_track(track: int) -> str:
    """Duplicate a track; the copy appears right after it."""
    return _call("duplicate_track", track=track)


@mcp.tool()
def set_track(track: Track, name: Optional[str] = None, mute: Optional[bool] = None,
              solo: Optional[bool] = None, arm: Optional[bool] = None,
              volume: Optional[float] = None, pan: Optional[float] = None,
              sends: Optional[list[Optional[float]]] = None,
              color_index: Optional[int] = None) -> str:
    """Change track name, mute/solo/arm, volume (0-1 fader, 0.85 = 0 dB),
    pan (-1..1) and send levels (list per return, 0-1, null = unchanged)."""
    return _call("set_track", track=track, name=name, mute=mute, solo=solo, arm=arm,
                 volume=volume, pan=pan, sends=sends, color_index=color_index)


@mcp.tool()
def group_tracks(tracks: list[int], name: Optional[str] = None) -> str:
    """Group tracks, where this Live version allows scripts to do it. If not,
    the error tells the user how to do it by hand (Cmd/Ctrl+G)."""
    return _call("group_tracks", tracks=tracks, name=name)


# -- clips & MIDI ---------------------------------------------------------------
@mcp.tool()
def create_clip(track: Track, slot: int, length: float = 4.0, name: Optional[str] = None) -> str:
    """Create an empty MIDI clip of `length` beats in a Session View slot."""
    return _call("create_clip", track=track, slot=slot, length=length, name=name)


@mcp.tool()
def delete_clip(track: Track, slot: int) -> str:
    """Delete the clip in a slot."""
    return _call("delete_clip", track=track, slot=slot)


@mcp.tool()
def duplicate_clip(track: Track, slot: int, target_slot: int) -> str:
    """Copy a clip to another slot on the same track (e.g. to make a variation)."""
    return _call("duplicate_clip", track=track, slot=slot, target_slot=target_slot)


@mcp.tool()
def set_clip(track: Track, slot: int, name: Optional[str] = None,
             loop_start: Optional[float] = None, loop_end: Optional[float] = None,
             looping: Optional[bool] = None, color_index: Optional[int] = None,
             gain: Optional[float] = None, pitch_coarse: Optional[int] = None,
             warping: Optional[bool] = None) -> str:
    """Edit clip properties. gain/pitch_coarse/warping apply to audio clips."""
    return _call("set_clip", track=track, slot=slot, name=name, loop_start=loop_start,
                 loop_end=loop_end, looping=looping, color_index=color_index, gain=gain,
                 pitch_coarse=pitch_coarse, warping=warping)


@mcp.tool()
def get_notes(track: Track, slot: int) -> str:
    """Read all notes of a MIDI clip (pitch, start_time, duration in beats, velocity)."""
    return _call("get_notes", track=track, slot=slot)


@mcp.tool()
def add_notes(track: Track, slot: int, notes: list[dict], replace: bool = False) -> str:
    """Write notes into a MIDI clip. Each note: {"pitch": 60, "start_time": 0.0,
    "duration": 0.5, "velocity": 100}. replace=True clears the clip first, which
    is how to edit existing notes: get_notes, modify, add_notes(replace=True)."""
    return _call("add_notes", track=track, slot=slot, notes=notes, replace=replace)


@mcp.tool()
def remove_notes(track: Track, slot: int, from_pitch: int = 0, pitch_span: int = 128,
                 from_time: float = 0.0, time_span: Optional[float] = None) -> str:
    """Remove notes inside a pitch/time range of a MIDI clip."""
    return _call("remove_notes", track=track, slot=slot, from_pitch=from_pitch,
                 pitch_span=pitch_span, from_time=from_time, time_span=time_span)


@mcp.tool()
def quantize_clip(track: Track, slot: int, grid: float = 0.25, amount: float = 1.0) -> str:
    """Quantize note starts to a grid in beats (0.25 = 1/16) with strength 0-1."""
    return _call("quantize_clip", track=track, slot=slot, grid=grid, amount=amount)


@mcp.tool()
def fire(track: Optional[Track] = None, slot: Optional[int] = None,
         scene: Optional[int] = None) -> str:
    """Launch a clip (track + slot) or a whole scene so the user can hear it."""
    return _call("fire", track=track, slot=slot, scene=scene)


@mcp.tool()
def stop_track(track: Track) -> str:
    """Stop clips playing on a track."""
    return _call("stop_track", track=track)


# -- scenes & arrangement -----------------------------------------------------------
@mcp.tool()
def create_scene(index: int = -1, name: Optional[str] = None) -> str:
    """Add a scene (a row of clips, e.g. 'Verse', 'Drop')."""
    return _call("create_scene", index=index, name=name)


@mcp.tool()
def set_scene(scene: int, name: Optional[str] = None, tempo: Optional[float] = None) -> str:
    """Rename a scene or set its tempo."""
    return _call("set_scene", scene=scene, name=name, tempo=tempo)


@mcp.tool()
def duplicate_scene(scene: int) -> str:
    """Duplicate a scene with all its clips (start of a new section)."""
    return _call("duplicate_scene", scene=scene)


@mcp.tool()
def build_arrangement(sections: list[dict], start_bar: int = 1) -> str:
    """Turn Session scenes into an Arrangement. sections is an ordered list of
    {"scene": i, "bars": 8, "mute_tracks": [track indexes to leave out]}. Clips
    are looped to fill each section. Typical flow for developing a loop: duplicate
    the loop scene into intro/build/drop/break variations, edit them, then call this."""
    return _call("build_arrangement", sections=sections, start_bar=start_bar)


# -- browser, instruments, plugins, samples --------------------------------------------
@mcp.tool()
def search_browser(query: str, category: Optional[str] = None, limit: int = 25) -> str:
    """Search Live's browser by name. category: instruments, audio_effects,
    midi_effects, drums, sounds, samples, clips, plugins (VST/AU), max_for_live,
    packs, user_library, user_folders (the user's own sample packs), or omit for all."""
    return _call("search_browser", query=query, category=category, limit=limit)


@mcp.tool()
def browse(category: str, path: str = "") -> str:
    """List one folder level of the browser, e.g. browse('user_folders', 'My Samples/Drums')."""
    return _call("browse", category=category, path=path)


@mcp.tool()
def load_item(uri: str, track: Track, slot: Optional[int] = None) -> str:
    """Load a browser item (instrument, effect, preset, plugin or sample) by uri
    onto a track; effects are appended to the end of its device chain. For a
    sample on an audio track, pass slot to place it as a clip."""
    return _call("load_item", uri=uri, track=track, slot=slot)


# -- devices & sound design --------------------------------------------------------------
@mcp.tool()
def get_devices(track: Track) -> str:
    """List a track's device chain (instruments, effects, racks, plugins)."""
    return _call("get_devices", track=track)


@mcp.tool()
def get_parameters(track: Track, device: Union[int, str]) -> str:
    """List a device's parameters with ranges and display values. Third-party
    plugins only expose parameters the user has configured/that the plugin publishes."""
    return _call("get_parameters", track=track, device=device)


@mcp.tool()
def set_parameter(track: Track, device: Union[int, str], parameter: Union[int, str],
                  value: Optional[float] = None, normalized: Optional[float] = None) -> str:
    """Set a device parameter by index or name, either in raw units (value) or
    as 0-1 of its range (normalized). Returns the new display value."""
    return _call("set_parameter", track=track, device=device, parameter=parameter,
                 value=value, normalized=normalized)


@mcp.tool()
def toggle_device(track: Track, device: Union[int, str], on: bool = True) -> str:
    """Turn a device on or off (bypass)."""
    return _call("toggle_device", track=track, device=device, on=on)


@mcp.tool()
def delete_device(track: Track, device: Union[int, str]) -> str:
    """Remove a device from a track."""
    return _call("delete_device", track=track, device=device)


# -- automation -------------------------------------------------------------------------
@mcp.tool()
def set_clip_automation(track: Track, slot: int, device: Union[int, str],
                        parameter: Union[int, str], points: list[dict],
                        clear: bool = True) -> str:
    """Write a clip automation envelope. points: [{"time": beats, "value": v}]
    in the parameter's raw units; each value holds until the next point. Use
    device='mixer' with parameter 'volume', 'pan' or 'send:N' for mixer moves."""
    return _call("set_clip_automation", track=track, slot=slot, device=device,
                 parameter=parameter, points=points, clear=clear)


@mcp.tool()
def clear_clip_automation(track: Track, slot: int) -> str:
    """Remove all automation envelopes from a clip."""
    return _call("clear_clip_automation", track=track, slot=slot)


# -- mixing & mastering -----------------------------------------------------------------
@mcp.tool()
def mix_snapshot() -> str:
    """All track volumes (with dB), pans, sends, devices and output meters, for
    mix/master advice. Start playback first so the meters read real levels."""
    return _call("mix_snapshot")


# -- Quick Loop + Shuffle -----------------------------------------------------------------
@mcp.tool()
def quick_loop(folder_query: str, track_name: str = "Quick Loop", pads: int = 6,
               bars: int = 2, density: float = 1.0, swing: float = 0.0,
               seed: Optional[int] = None, category: str = "user_folders") -> str:
    """Quick Loop: pick samples whose browser path contains folder_query (e.g.
    'techno drums'), load them into a new Drum Rack and write a pattern based on
    each sample's role (kick/snare/hat/...). density 0-2, swing 0-0.5. Returns
    the seed so the loop can be recalled."""
    return _call("quick_loop", folder_query=folder_query, track_name=track_name, pads=pads,
                 bars=bars, density=density, swing=swing, seed=seed, category=category)


@mcp.tool()
def shuffle_loop(track: int, seed: Optional[int] = None, density: Optional[float] = None,
                 swing: Optional[float] = None) -> str:
    """Shuffle: re-roll the pattern of a Quick Loop track, keeping its samples.
    Pass a previous seed to bring back a loop you liked."""
    return _call("shuffle_loop", track=track, seed=seed, density=density, swing=swing)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
