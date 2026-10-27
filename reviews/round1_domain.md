# Review round 1 — domain (FBDD, pocket similarity, PPI pockets, ligand labels)

Reviewer remit: prior-work coverage; fragment-docking arm; PPI benchmark; BLiPS labels.
Target: DESIGN.md v0 (2026-10-27 19:15). I did not edit DESIGN.md.

**Verdict.** The architecture (two tiers, index + re-rank), the choice of TOUGH-M1 as primary, the
zero-shot/trained separation and the leakage policy are right and follow LITERATURE §7 faithfully. Four
things are wrong or missing enough to change results: one large prior-work omission that makes part of the
PPI arm redundant and supplies its missing baseline; a docking arm that is pinned to the one scoring function
published at chance level on the primary benchmark and that dropped two of three size-control
recommendations from its own feasibility report; a PPI headline task that a fold baseline can solve by
construction; and ligand-sharing labels at a noise level the literature has already measured.

## 1. Prior work

**The Pasteur PPI pocketome is absent from DESIGN entirely** (LITERATURE §2.2, §5, §7.9 all flag it). I
verified the live REST API today: `ippidb.pasteur.fr/api/cavity/` = **23,238 VolSite cavities served as mol2
pharmacophore-typed point clouds**, with `type` = orthosteric / allosteric (PLOC/PLONC/PLA), chain, UniProt,
organism and ~109 shape/chemistry descriptors per cavity; `api/hotspot/` = 123,117 hot-spot residues;
`api/distance/` = **1,813,044 precomputed cavity–cavity records**, i.e. the PSI pocket-similarity matrix.
Bulk mirror: Zenodo 10.5281/zenodo.10805580, CC-BY-4.0. Consequences: (a) PSI (109 descriptors + similarity)
is architecturally B1 for interface pockets and is the **must-have PPI baseline**; (b) a ligand-sharing PPI
positive set — the one that actually speaks to off-target/repurposing — can be built from these cavities
plus their ligands, which is a far better headline than interologs; (c) the hot-spot annotations give a
principled interface-pocket weighting. Also missing from §2.4: BURROW's own 400-assembly dimer benchmark
(`pocket_detect/data/processed/dimer`), which `reports/ppi_dimers.md` §4(c) recommends.

**Missing runnable external baselines.** C1/C2/C3 are all stated against B1 (our own size-free descriptor
cosine). Beating our own trivial baseline by 0.03 is not a result. EPoCS (Apache-2.0, training-free, pip)
and PocketVec's *precomputed* descriptors (MIT mirror `sbnb-irb/PocketVec`) are both cheap and run on our
pocket definition; APoc is already B2. At least one must be a headline comparator. ProFSA zero-shot (0.82 on
TOUGH-M1) is the number our untrained method is actually competing with.

**Unnamed prior art for two arms.** A3 is ProCare (point-cloud registration + ICP on pharmacophore-annotated
cavity points, J Med Chem 2020) and VolSite/Shaper; the novelty is the GPU batch, which should be stated as
such. A4's objective has been done: **ErePOC** (Nat Commun) trains ESM-2 contrastively on 326k BioLiP2
pocket–ligand pairs with a KL loss **aligning pocket cosine to the ligand-Tanimoto distribution** — a graded
target, strictly better specified than A4's binary positives. Adopt the graded loss and cite.

**Novelty claim that survives checking.** I searched for docking-pose interaction-fingerprint *panels* used
as a pocket descriptor. IFPs are standard for pose filtering and for comparing poses in one site (SIFt,
PADIF, Tc-IFP), but I found nothing using a fixed probe panel's pose-contact profile as a transferable
pocket descriptor. A2(c) is genuinely unclaimed and is the right thing to bet on.

## 2. Fragment-docking arm

**The scoring function is the problem.** §2.6 pins stock Vina. A plain Vina docking profile scores **0.55 on
TOUGH-M1** vs rDock **0.67** [LITERATURE §3.2, P] — this is the single most relevant published result for
A2 and the go/no-go gate ignores it. "≥ B0 + 0.05" can be cleared by a size proxy. The gate must be the
Govindaraj & Brylinski replication specified in LITERATURE §7.6 (FDA-drug rank vectors, Spearman ρ) against
the 0.55/0.67 anchors, with A2(c) pose features as the stated remedy if ADock behaves like Vina.

**Box definition reintroduces the confound the feasibility study measured.** §3 A2 uses "box from pocket
points + 4 Å", so box volume is a deterministic function of pocket size, and mean fragment score already
tracks volume at ρ −0.74 / point count −0.83. PocketVec used a **fixed 12 Å box**. Use a fixed-size cubic box
on the pocket centroid; keep the extent-based box as an ablation only. Two of the three normalisations the
feasibility report asked for are also missing: a heavy-atom-narrowed panel (10–14 HA) and ligand-efficiency
(score per heavy atom) scores. "dz" alone leaves PC1 = 43 % variance tracking volume.

**Panel selection.** 64 MaxMin picks on Morgan FPs from NCI `first_5K` maximise scaffold diversity but
under-sample charged and strongly polar fragments — and the only convincing discrimination in the
feasibility run (trypsin S1 vs apolar pockets) is exactly the charge axis. Stratify the pick over
pharmacophore class (cation / anion / HBD-rich / HBA-rich / aromatic apolar / aliphatic apolar) × heavy-atom
bin, MaxMin within strata, and prefer a recognised fragment library (Enamine/Astex/DSi-poised or ZINC
"frags") with licence in DATA.md. Rigid docking is fine given the ≤3 rotatable-bond filter.

**Non-binder bins are undefined for Vina.** PocketVec's ranks 129/130/131 rely on rDock's *positive* scores;
Vina scores are essentially always negative, so variant (a) is not PocketVec's method until a non-binder
criterion is fixed (e.g. score > −3.5 kcal/mol, or buried fraction < 0.5 / pose centroid outside the pocket
point set). Fix it before freezing.

**The pose arm needs its own control.** Seed reproducibility was measured for *scores* (r 0.98 after dz),
never for *poses*. Add to §5: top-pose RMSD across seeds and across the 3 Å/5 Å pocket perturbation; if it is
poor, use Boltzmann-weighted contacts over the top-3 poses rather than the single best pose.

## 3. PPI benchmark

**P-ortho measures conservation, not fold-independent similarity.** Interolog interface pockets share a fold
by construction, so B0' (Foldseek/US-align) is near-ceiling on P-ortho and C3 as written is easy and
uninformative. Keep P-ortho as a *robustness/invariance* tier (with P-sym) and make the headline PPI task
ligand-sharing across unrelated interfaces, from the iPPI-DB/Pasteur cavities. Report Foldseek-TM ranking as
the baseline for every PPI number, and add **iAlign / IS-score** — the canonical interface-similarity
baseline, currently absent.

**"Similar PPI pocket" for off-target work** means "would bind the same chemotype", and the field's own
chemotypes (14-3-3 stabilisers, Bcl-2/Bcl-xL/Mcl-1 BH3 grooves, bromodomain KAc sites, MDM2/MDMX) give
cross-family positives that are not interologs. iPPI-DB's ligand and cavity tables make that set
constructible; 2P2I-DB and TIMBAL should be deleted from §2.4 (both dead per `reports/ppi_dimers.md`).

**Negatives** must be matched on f_min and buriedness as well as volume, else interface vs non-interface is
trivially separable. Also record that AFDB dimers may be templated on the PDB complexes used in P-lig.

**Deployment caveat belongs in the design:** 85.8 % of interface pockets are absent from monomer output and
48.8 % are PPI-created. The human-monomer AFDB demo therefore cannot find PPI pockets; run the scale demo on
a dimer set too.

## 4. BLiPS ligand-sharing labels

**One shared ligand is too weak a label.** PocketVec measured this directly [P]: one shared PDB ligand gives
AUROC **0.58**; ≥3 shared ligands **0.75**; ProSPECCTs identical-cofactor sets 0.64/0.62. Their own
conclusion is that "two binding sites having identical crystallized ligands are not necessarily similar".
Headline positives should require ≥2 (preferably ≥3) shared or Tc ≥ 0.7 ligands, with AUC stratified by the
number of shared ligands.

**Cofactor bias is structural, not cosmetic.** Requiring different folds means the surviving cross-fold
positives are almost entirely promiscuous cofactors (ATP/NAD/FAD/SAM/haem) — the very class the chemotype cap
then suppresses. Count the positives before freezing; report with and without the top-20 promiscuous CCDs. For
cofactors only a *sub-pocket* is conserved (adenine subsite in Rossmann vs kinase hinge), so a site-level
label is partly wrong; a sub-pocket/ligand-fragment correspondence (KRIPO-style) for that class would be more
honest than a whole-site label.

**Thresholds.** ECFP4 Tanimoto is unstable below ~10 heavy atoms; require ≥10–12 HA (MW ≥ 150) of any
label-bearing ligand, otherwise both the 0.7 and 0.3 cut-offs are size artefacts. The ≥0.7 / <0.3 pair and
the additive/ion exclusions are otherwise sensible, and the size-matched negatives are the right control.
Negatives at max Tc < 0.3 assert non-binding purely from deposition absence (the known TOUGH-M1 ceiling): add
a functional discriminator (different EC 3rd level, or no shared ChEMBL active) and state the ceiling.

## 5. Could (not blocking)

- The AF-model re-run of ProSPECCTs D1/D2/D7 and a TOUGH-M1 subset (LITERATURE "bonus experiment", cheap and
  unclaimed) is not in §2.5; it fits the robustness section.
- Match fragments vs lead-like on *compute* as well as N, and pre-register the PPI sub-hypothesis (fragments
  win on shallow pockets) as a one-sided test stratified by volume/buriedness, where it is detectable.
- KLIFS kinase pockets as a fine-grained hard-negative tier.
- Report a PLM-only baseline (EPoCS or PocketScope) to quantify how much of each benchmark is solvable from
  sequence alone — a confounder control, not a competitor.
