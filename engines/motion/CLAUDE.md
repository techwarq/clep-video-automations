# pipeline_motion

Read the plan and context before working here:

@AGENT_PLAN.md

Key decisions to remember (details in the plan):
- No paid model calls or media without a cost estimate and an explicit yes. The user has had $0 credits; use
  `motion.py film … --dry` (scripted, $0) to test the loop.
- The model never gets reference code, only the craft ESSENCE (`film3/skills/05_craft.md`).
- Target: a 40 s film under $1 of model cost. Target server: a small VM (4 vCPU / 4 GB), where today's renderer
  runs out of memory at 3 workers. Use one render queue with capped browser slots, never parallel renders.
- `film3/hybrid.py` is an unfinished experiment (section 6); its benchmark in `bench/` is the next step.
- Docker on this Mac also runs the user's other projects: only touch containers from the `motion-bench` image.
