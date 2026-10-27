# LESSONS — process rules (one line each, with evidence)

Inherited from pocket_detect (LESSONS.md there):
1. Inspect mounts, tools and real resource caps first. (pocket_detect is read-only here → .pth import, 2026-10-27)
2. Run jobs > ~5 min detached with log + completion marker; kill only stored PIDs, never `pkill -f`.
3. Reproduce published numbers before building on an evaluation harness.
4. "Done" for data/leakage work needs an independent re-implementation.
5. Every mechanism or negative claim needs a control; decompose headline gains by composition (e.g. ions).
6. Seal test labels technically (move + chmod) BEFORE launching any agent, including reviewers. (A statistics
   reviewer opened TOUGH-M1 pair labels 2 min before sealing; DEV1, 2026-10-27.)
