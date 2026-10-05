"""Audio mix from the composition's declared cues.

Sources: the project's voice.wav (always at t=0), R.music(...) beds from
library/music, R.sfx(...) hits from library/sfx, and R.clipAudio(...) slices of
a footage clip's own sound. Music ducks under the voice; the mix is loudness-
normalised to -14 LUFS (the Reels/TikTok/Shorts target).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from reels import config

SR = 48000


def _lib(folder: Path, name: str) -> Path | None:
    p = Path(name).expanduser()
    if p.is_file():
        return p
    for ext in (".mp3", ".wav", ".m4a"):
        if (folder / f"{name}{ext}").exists():
            return folder / f"{name}{ext}"
    return None


def library() -> dict:
    return {"music": sorted(p.stem for p in config.MUSIC_DIR.glob("*.mp3")),
            "sfx": sorted(p.stem for p in config.SFX_DIR.glob("*.mp3"))}


def mix(project, cues: list[dict], dur: float) -> Path:
    out = project.root / ".render" / "mix.wav"
    out.parent.mkdir(exist_ok=True)
    inputs: list[str] = []
    graph: list[str] = []
    voice_label, beds, layers = None, [], []

    def add_input(*args: str) -> int:
        inputs.extend(args)
        return sum(1 for a in inputs if a == "-i") - 1

    voice = project.root / "voice.wav"
    if voice.exists():
        i = add_input("-i", str(voice))
        graph.append(f"[{i}:a]aresample={SR},highpass=f=70,"
                     "acompressor=threshold=0.12:ratio=3:attack=5:release=90:makeup=1.4,"
                     "aformat=channel_layouts=stereo,asplit=2[vo][vokey]")
        voice_label = "[vo]"

    for n, c in enumerate(cues):
        at_ms = max(0, int(float(c.get("at", 0)) * 1000))
        gain = float(c.get("gain", 0.6))
        if c["kind"] == "music":
            src = _lib(config.MUSIC_DIR, c["name"])
            if not src:
                print(f"[audio] unknown music {c['name']!r} — skipped")
                continue
            i = add_input("-stream_loop", "-1", "-i", str(src))
            length = max(0.1, dur - float(c.get("at", 0)))
            graph.append(f"[{i}:a]aresample={SR},aformat=channel_layouts=stereo,"
                         f"atrim=start={float(c.get('from', 0)):.3f}:duration={length:.3f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d=0.25,afade=t=out:st={max(0.0, length - 1.2):.3f}:d=1.2,"
                         f"volume={gain:.3f},adelay={at_ms}|{at_ms}[m{n}]")
            beds.append(f"[m{n}]")
        elif c["kind"] == "sfx":
            src = _lib(config.SFX_DIR, c["name"])
            if not src:
                print(f"[audio] unknown sfx {c['name']!r} — skipped")
                continue
            i = add_input("-i", str(src))
            graph.append(f"[{i}:a]aresample={SR},aformat=channel_layouts=stereo,"
                         f"volume={gain:.3f},adelay={at_ms}|{at_ms}[s{n}]")
            layers.append(f"[s{n}]")
        elif c["kind"] == "clip":
            m = project.media.get(c["key"])
            if not m or not m.get("audio"):
                print(f"[audio] clip {c['key']!r} has no audio — skipped")
                continue
            start = float(m.get("start", 0)) + float(c.get("from", 0))
            length = float(c.get("dur") or (dur - float(c.get("at", 0))))
            i = add_input("-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", m["path"])
            graph.append(f"[{i}:a]aresample={SR},aformat=channel_layouts=stereo,afade=t=in:d=0.04,"
                         f"afade=t=out:st={max(0.0, length - 0.1):.3f}:d=0.1,"
                         f"volume={gain:.3f},adelay={at_ms}|{at_ms}[c{n}]")
            layers.append(f"[c{n}]")

    if beds:
        graph.append("".join(beds) + f"amix=inputs={len(beds)}:normalize=0[bed]")
        if voice_label:   # duck the music under the voice
            graph.append("[bed][vokey]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=320[bedd]")
            layers.append("[bedd]")
        else:
            layers.append("[bed]")
    elif voice_label:
        graph.append("[vokey]anullsink")
    if voice_label:
        layers.insert(0, voice_label)

    if not layers:   # still ship an audio track: platforms treat silent-trackless files oddly
        subprocess.run([config.FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"anullsrc=r={SR}:cl=stereo", "-t", f"{dur:.3f}", str(out)], check=True)
        return out
    graph.append("".join(layers) + f"amix=inputs={len(layers)}:normalize=0:duration=longest,"
                 f"apad,atrim=duration={dur:.3f},loudnorm=I=-14:TP=-1.5:LRA=11,aresample={SR}[aout]")
    subprocess.run([config.FFMPEG, "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(graph),
                    "-map", "[aout]", "-ac", "2", str(out)], check=True)
    print(f"[audio] mixed voice={'yes' if voice_label else 'no'}, {len(beds)} music, "
          f"{len(layers) - (1 if voice_label else 0) - (1 if beds else 0)} sfx/clip cue(s)")
    return out
