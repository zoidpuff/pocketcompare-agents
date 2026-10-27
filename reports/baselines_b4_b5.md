# Baselines B4 (ESM-2 650M lining-residue mean) and B5 (EPoCS) on TOUGH-M1 — 2026-10-27

## B4 — works, full coverage
- `src/pocketcompare/descriptors/esm_pocket.py`, `scripts/compute_esm.py --dataset tough_m1`, `tests/test_esm_pocket.py` (4 pass, GPU test incl.).
- Model `facebook/esm2_t33_650M_UR50D` (HF transformers, fp16 forward, last hidden layer, BOS/EOS dropped), per-chain embeddings cached as fp16 per unique sequence (sha1) in `data/processed/esm/esm2_t33_650M_UR50D/` (5.5 GB, git-ignored, reusable by other datasets).
- Sequence/numbering from gemmi (amino-acid residues in file order, first altloc); lining residues `chain:num[icode]` are mapped through the file's residue list, never by offset; if the chain letter is absent and the file has one protein chain, that chain is used (the adapter's single-chain remap). Chains >1022 aa: windows of 1022, stride 511, last window end-aligned, per-residue average over covering windows (implemented and unit-tested; no TOUGH-M1 chain exceeds 993 aa, so not exercised on real data).
- Output `data/processed/descriptors/tough_m1/b4_esm2_{L,D}.npy` (7524x1280 each) + `b4_esm2_ids.parquet` + `b4_esm2_provenance.json`. D = union of residues of the matched merged pocket(s) (`d_members`, from the point cache `pk_residues`). 7524/7524 have L and D; 0 lining residues missing; all files single-chain. D includes 1456 pockets flagged `D_missed` (coverage < 0.3) — filter with that column if wanted.
- Timing: 508 s wall for all 7524 (incl. embedding, 1 GPU); per pocket median 0.059 s, mean 0.066 s (embedding of new sequences included).

## B5 — EPoCS works (option 1), full coverage
- Installed in separate venv `envs/epocs` (py3.10); needed: fair-esm, biopandas, pymol-open-source (PyPI wheel) + libX11/GL from conda-forge via micromamba (`envs/x11`). Details, commit bc9e15c, licence (Apache-2.0), ESM-2 3B weight sha256 in DATA.md "External baselines".
- Patches/workarounds (no source edits): `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` (torch 2.6 vs fair-esm checkpoints); `tmap` from PyPI is the wrong API so clustering/atlas step crashes — irrelevant, we only use `pocket_embeddings/*.pkl`; EPoCS then computes an unneeded 7524^2 distance matrix, which we killed. Pitfall: overwriting `LD_LIBRARY_PATH` silently disables CUDA here (first full attempt ran on CPU; aborted and rerun) — always append.
- 20-pocket sample ran (1 m 45 s incl. 3B model load); full run: all 7524 pockets embedded (2560-d, ESM-2 3B, Voronoi pocket residues from the shipped ligand), 0 failures, no sequences rejected. Wall ~38 min on cuda:1 + 8 CPU procs (ESM 3B stage ~25 min, 8 model reloads of 1000 seqs; pocket extraction ~6 min) => ~0.3 s/pocket.
- Output `b5_epocs.npy` (7524x2560), `b5_epocs_ids.parquet`, `b5_epocs_provenance.json` (via `scripts/collect_epocs.py`). Metric as published: Euclidean distance.
- Sanity: Spearman 0.73 between pairwise EPoCS distances and B4 cosine distances on 500 random pockets.
- Caveat: EPoCS defines the pocket from the ligand (Voronoi tessellation, 8 A) = L-mode only; no D-mode variant. Raw run dir `data/processed/epocs/full` (22 GB, mostly per-chain fp32 embeddings) can be deleted after use.
- PocketVec / APoc fallbacks were not needed.
