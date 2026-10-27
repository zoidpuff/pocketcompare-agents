# Review round 1 — external PI (overall scientific strategy) — DESIGN.md v0

**Verdict.** The evaluation discipline is strong: sealed tests, a fold-dead primary benchmark, a size-matched negative set and a missing-pocket policy. The method portfolio is too large for ~22 h, though, and the claims are anchored to a weak internal baseline. It is also missing the arm most likely to beat everything here cheaply: a pooled protein-language-model (PLM) embedding over the pocket residues. The PPI part as written tests homology recovery, not fold-independent similarity. Novelty is real in three places only: the pose-interaction docking profile, a leakage-controlled PPI-pocket benchmark, and AF-model robustness plus an AFDB-scale ANN index. A1 is FuzCav/PocketMatch on volume points, A3 is essentially SiteHopper (ROCS on pockets) and A4 is DeeplyTough-like. Say so in DESIGN.md.

## Changes, ranked

### MUST

**M1. Cut scope to a critical path (§3, §8).** A1 and A4b (the learned metric on A1) are the main tier-1 bets. A2 is the tier-2 bet, gated. Demote A3 and full A4 (EGNN) to *could*: start them only if A1, A2 and A4b are scored on dev by 03:00. Run fragments vs lead-like at one size (N = 128), not two. Re-check the lead-like docking preset: `frag_lite_np` was only validated on fragments, so measure seed r on 20 lead-likes first. Drop "two models of the same complex" from PPIPS, because they do not exist. *Why:* five arms, two new benchmarks, robustness sets and an AFDB demo do not fit in 22 h with independent verification. *Effect:* each remaining arm gets tuned properly instead of being half-built. *Cost:* none; it saves about 6–8 agent-hours.

**M2. Add a PLM-pocket arm, used as both baseline and fusion input (§3).** Mean-pool ESM-2 (650M, or 3B as in EPoCS) residue embeddings over the BURROW pocket-lining residues and compare by cosine. This is EPoCS on our pockets; PocketScope claims rank 1 on ProSPECCTs with the same idea. It is FAISS-ready. Add it as **B4 (must-beat)** and as a fusion input. For PPI pockets, embed each chain separately: the embeddings lack partner context, which is exactly where geometry should win. Pre-register that as a hypothesis. *Why:* a tool that loses to an off-the-shelf training-free baseline it never ran would be the first reviewer objection. *Cost:* about 1–2 GPU-h for about 30k chains, plus 1 agent-hour. Check that the weights can be fetched now.

**M3. Fix the claims (§0).** (a) State which pocket mode C1 uses. I suggest L-mode as primary and D-mode as co-reported, with the same test. (b) C1 must also beat **B4 (PLM)** and **B0' (TM-score)**, not only B1. B1 is our own weakest descriptor, so beating it by 0.03 says little. (c) Add C5 (AF robustness, see S2). (d) Write the margin test explicitly as H0: Δ ≤ 0.03. *Effect:* claims that an outside reader would find meaningful.

**M4. Make the PPI task fold-honest (§2.4).** For interologs, global fold alone finds the right complex, so P-ortho against random negatives would be solved by Foldseek. Make the headline PPI metric **within-complex-pair correspondence**: given an interface pocket in complex X, rank all pockets of interolog X′ and check whether the corresponding one is at the top. Fold cannot help with that. Score with **best-over-overlapping pockets at site level**, because BURROW re-segments the same site 40–45 % of the time. Then require C3 to beat B0' and B4 on the cross-complex version. In REPORT, call the PPI result "transfer to interface pockets", not fold-independent PPI similarity, unless S1 delivers.

**M5. Extend leakage rules to every trained component (§2.3, §2.6).** If A4b or the fusion is fit on TOUGH-M1-dev, filter TOUGH-M1-dev against ProSPECCTs, Vertex and PPI-test with the same MMseqs2 + Foldseek rule. Known PDB overlaps: 355 with ProSPECCTs, 320 between ProSPECCTs and Vertex. Also report the size of the largest merged cluster component in the TOUGH-M1 split. Rossmann and TIM-barrel folds can make a 30/70 split lopsided.

### SHOULD

**S1. Add the Pasteur PPI-pocket set (Moine-Franel 2024, CC-BY, about 11 GB) as an external PPI test with real ligands.** It has experimental interface pockets with PLOC/PLONC labels. Ligand-sharing pockets across different families give a genuinely fold-independent PPI test, and their 109-descriptor PSI is a direct baseline for B1/A1. This is LITERATURE.md §7 rec. 9, but it was dropped from the design. *Cost:* one data agent for about 2 h. If the download fails, record that and fall back to iPPI-DB.

**S2. Promote AF robustness to a claim (C5) and add a deployment-realistic retrieval test.** (a) TOUGH-M1-test and ProSPECCTs D1/D2/D7 rebuilt on AFDB models: report ΔAUC holo→AF. Nobody has published this, and it is our deployment domain. (b) D-mode currently picks the detected pocket using ligand overlap, which is an oracle and inflates D-mode. Add a blind retrieval test instead: plant each test query's partner pockets among about 100k D-mode human-proteome pockets (BURROW full list, about 3 min to compute), then report top-k and enrichment. That is the real FAISS use case, and it exposes metal-site and junk-pocket domination. Decide the metal-pocket handling for the index here. *Cost:* about 2 agent-hours.

**S3. Fix A2's size problem by design, not after the fact.** Pre-register per-heavy-atom (ligand-efficiency) scoring and a heavy-atom-matched fragment panel (10–14 heavy atoms) as variant (d). Run A2 on all of TOUGH-M1-dev rather than 2,000 pockets; at roughly 150 pockets/s/node that is under 2 min. The gate should require A2 to add value **over A1 + B4**, not over B0.

**S4. Treat BLiPS as training data first.** Keep its test split, as the brief requires, but make no headline claim on it. Do not let building it block A1/A4b: TOUGH-M1-dev can serve as the first training set for A4b.

### COULD

**C1. Move the freeze to 11:00.** Report drafting can run in parallel from 06:00.

**C2. Report Vertex in D-mode only.** Its ligand-instance ambiguity (627 site indices without a matching HET copy) makes L-mode ill-defined.

**C3. Add a "PPI pocket → known ligand pocket" lookup demo.** Find the nearest BLiPS ligand sites for interface pockets. This is the application story for the PPI part.
