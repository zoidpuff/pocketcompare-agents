# LESSONS — process rules (one line each, with evidence)

Inherited from pocket_detect (LESSONS.md there):
1. Inspect mounts, tools and real resource caps first. (pocket_detect is read-only here → .pth import, 2026-10-27)
2. Run jobs > ~5 min detached with log + completion marker; kill only stored PIDs, never `pkill -f`.
3. Reproduce published numbers before building on an evaluation harness.
4. "Done" for data/leakage work needs an independent re-implementation.
5. Every mechanism or negative claim needs a control; decompose headline gains by composition (e.g. ions).
6. Seal test labels technically (move + chmod) BEFORE launching any agent, including reviewers. (A statistics
   reviewer opened TOUGH-M1 pair labels 2 min before sealing; DEV1, 2026-10-27.)
7. Always evaluate in the deployment pocket definition (detected pockets) next to the ligand-defined one: a 4 Å
   ligand shell imprints ligand shape and inflated A1 from 0.56 (D) to 0.81 (L) on the same pairs (D11).
8. Run the size-only baseline first on any pocket-pair benchmark: B0 alone reached ROC 0.78 on TOUGH-M1-dev;
   stratified AUC is the only number that separates descriptor signal from size (dev eval, 21:45).
9. Pre-registered gates save time: A2 docking failed its gate in one run and stopped consuming effort (D10).
