# NC17 Assistant for Ableton Live

An AI production assistant inside Ableton Live 12. It connects **Claude Code** and
**ChatGPT Codex** to your open Live Set through MCP, so you can describe what you
want in plain language: turn a loop into an arrangement, edit MIDI, add samples
from your own packs, shape sounds, build effects chains, write automation, or get
help with mixing and mastering. Every change goes through Live's own API, so it
lands in Live's undo history and your project stays fully editable.

Includes **Quick Loop + Shuffle**, a tool for generating sample-based ideas.

```
Claude Code / Codex ──MCP (stdio)──> nc17-ableton server ──JSON over 127.0.0.1:9877──> NC17Assistant Remote Script (inside Live)
```

## Requirements

- Ableton Live 12 (macOS or Windows). Some features need Live 11+ APIs.
- Python 3.10+ (for the MCP server)
- Claude Code and/or Codex with an active subscription or API access

Live, plugins and subscriptions are not included.

## Install

**macOS**

```bash
./install/install-macos.sh
```

**Windows** (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File install\install-windows.ps1
```

The installer:
1. copies `NC17Assistant` into your User Library `Remote Scripts` folder,
2. installs the MCP server into `~/.nc17-ableton`,
3. registers it with `claude mcp add` and `codex mcp add` if those CLIs are installed.

Then in Live: **Settings → Link, Tempo & MIDI → Control Surface → NC17Assistant**.
Live shows "NC17 Assistant ready" in its status bar.

To register by hand:

```bash
claude mcp add nc17-ableton -s user -- ~/.nc17-ableton/bin/nc17-ableton
codex mcp add nc17-ableton -- ~/.nc17-ableton/bin/nc17-ableton
```

## What you can ask

- "Develop the loop in scene 1 into a 64-bar arrangement: intro, build, drop, break, outro."
- "Write a bassline on track 2 that follows the chords in the keys clip, in F minor."
- "Find a snappy clap in my samples and add it to the drum rack groove."
- "Put Operator on a new track and make a warm pad, then add Chorus and a long reverb."
- "Automate the filter on the lead to open over 8 bars."
- "Play the song and tell me which tracks are fighting in the low end."
- "Quick loop from my 'lofi drums' folder, 2 bars, a bit of swing. Shuffle it until it's good."

## Tools

| Area | Tools |
|---|---|
| Session | `get_session`, `set_song`, `transport` (play/stop/undo/redo) |
| Tracks | `create_track`, `delete_track`, `duplicate_track`, `set_track` (name, mute, solo, arm, volume, pan, sends), `group_tracks`* |
| Clips & MIDI | `create_clip`, `delete_clip`, `duplicate_clip`, `set_clip`, `get_notes`, `add_notes`, `remove_notes`, `quantize_clip`, `fire`, `stop_track` |
| Arrangement | `create_scene`, `set_scene`, `duplicate_scene`, `build_arrangement` |
| Sounds | `search_browser`, `browse`, `load_item`: Live devices, presets, VST/AU plugins, Max for Live, packs, your sample folders |
| Devices | `get_devices`, `get_parameters`, `set_parameter`, `toggle_device`, `delete_device` |
| Automation | `set_clip_automation` (device parameters and mixer volume/pan/sends), `clear_clip_automation` |
| Mixing | `mix_snapshot` (levels in dB, meters, sends, chains) |
| Quick Loop + Shuffle | `quick_loop`, `shuffle_loop` |

### Quick Loop + Shuffle

`quick_loop` finds samples whose browser path matches your words (by default in
your own sample folders, added in Live's browser under *Places*). It picks a
varied set (kick, snare, hats, perc...), loads them into a new Drum Rack and
writes a groove based on each sample's role. `shuffle_loop` re-rolls the groove
with the same samples. Every loop has a seed, so you can bring back one you liked.

## Limits

These come from Live's scripting API, not from the assistant:

- **Grouping**: Live 12 doesn't let scripts create groups, so `group_tracks` tells you to press Cmd/Ctrl+G instead (it uses the API call if a future Live adds one).
- **Automation**: clip envelopes only (Session clips). The API can't write Arrangement automation lanes.
- **Third-party plugins**: only the parameters the plugin exposes to Live, or the ones you've configured with *Configure*.
- **Audio analysis**: meters are the only signal; the assistant can't listen to the audio itself.
- `build_arrangement` loops clips to fill each section. A clip longer than its section can overrun the section end, so trim it in Live if needed.

## Security

The Remote Script listens on `127.0.0.1` only, so nothing outside your computer
can connect to it.

## Development

```bash
python3 -m unittest discover -s tests -v
```

The tests use fake Live objects (`tests/fakelive.py`) to run the command handlers,
the pattern generator, the socket client and the MCP tool registration.
You can only test the real behaviour inside Live. The Remote Script logs to
Live's `Log.txt`.
