"""Quick Loop + Shuffle: pure pattern logic (no Live imports, unit-tested).

Samples are assigned to drum pads; each gets a step pattern chosen from a
role inferred from its file name. Same seed -> same loop.
"""
import random

FIRST_PAD = 36  # C1, first Drum Rack pad
STEPS_PER_BEAT = 4

ROLE_KEYWORDS = [
    ("kick", ("kick", "kik", "bd", "bassdrum")),
    ("snare", ("snare", "snr", "sd", "rim")),
    ("clap", ("clap", "clp")),
    ("hat", ("hat", "hh", "hihat", "shaker", "ride", "cym")),
    ("perc", ("perc", "tom", "conga", "bongo", "cowbell", "tamb", "click")),
    ("bass", ("bass", "sub", "808")),
    ("fx", ("fx", "riser", "impact", "sweep", "noise")),
]

# Per-16th-step hit probability for one bar of 4/4, plus velocity range.
ROLE_PROFILES = {
    "kick": ([.95, 0, .05, .1, .3, 0, .15, 0, .85, 0, .2, .1, .3, 0, .25, .05], (100, 127)),
    "snare": ([0, 0, 0, 0, .95, 0, 0, .1, 0, .05, 0, 0, .95, 0, .15, .2], (95, 120)),
    "clap": ([0, 0, 0, 0, .9, 0, 0, 0, 0, 0, 0, .1, .9, 0, 0, .1], (90, 115)),
    "hat": ([.6, .3, .85, .35] * 4, (55, 100)),
    "perc": ([.1, .2, .25, .3] * 4, (60, 105)),
    "bass": ([.7, 0, .2, .35, .1, .3, .2, 0] * 2, (90, 120)),
    "fx": ([.3] + [0] * 15, (70, 100)),
    "other": ([.2, .1, .25, .15] * 4, (60, 110)),
}


def infer_role(name):
    lowered = name.lower()
    for role, words in ROLE_KEYWORDS:
        for w in words:
            if w in lowered:
                return role
    return "other"


def pick_samples(names, count, seed):
    """Pick up to `count` sample names, preferring one of each role."""
    rng = random.Random(seed)
    pool = list(names)
    rng.shuffle(pool)
    chosen, roles = [], set()
    for n in pool:
        r = infer_role(n)
        if r not in roles:
            chosen.append(n)
            roles.add(r)
        if len(chosen) >= count:
            return chosen
    for n in pool:
        if n not in chosen:
            chosen.append(n)
        if len(chosen) >= count:
            break
    return chosen


def generate_pattern(sample_names, seed, bars=2, density=1.0, swing=0.0, beats_per_bar=4):
    """Return Live-style note dicts for a loop of `bars` bars.

    density scales hit probability (0..2); swing (0..0.5) delays off-beat 16ths.
    """
    rng = random.Random(seed)
    steps_per_bar = beats_per_bar * STEPS_PER_BEAT
    step_len = 1.0 / STEPS_PER_BEAT
    notes = []
    for pad, name in enumerate(sample_names):
        probs, (vmin, vmax) = ROLE_PROFILES[infer_role(name)]
        pitch = FIRST_PAD + pad
        for bar in range(bars):
            for step in range(steps_per_bar):
                p = min(1.0, probs[step % len(probs)] * density)
                if p <= 0 or rng.random() >= p:
                    continue
                start = (bar * steps_per_bar + step) * step_len
                if step % 2 == 1:
                    start += swing * step_len
                notes.append({
                    "pitch": pitch,
                    "start_time": round(start, 6),
                    "duration": step_len * (0.9 if step % 2 else 1.0),
                    "velocity": rng.randint(vmin, vmax),
                })
    notes.sort(key=lambda n: (n["start_time"], n["pitch"]))
    return notes
