# engines

The video engines, copied from `allore-pipelines` (code, skills and libraries only — no venvs, renders or
old projects). The VM services call them as CLIs; in Docker they share one Python env.

| folder | source | CLI the VM calls |
|---|---|---|
| `reels/` | `allore-pipelines/pipeline` | `python -m reels make "<prompt>" --out <mp4> --yes` |
| `motion/` | `allore-pipelines/pipeline_motion` | `python motion.py film <job_id> --url <url> --request "<text>" --yes` |

`motion/handbuilt/` keeps only the four reference films the agent reads (`film.html` + small assets);
frame sequences, wavs and finals were left out.
