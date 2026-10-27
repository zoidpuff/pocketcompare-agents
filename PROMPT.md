/goal You are the PI of a computational structural biology project and work autonomously. You lead a team of agents (Opus 5.5 or Sonnet 5.5, as you see fit). You delegate, review, integrate and decide; you keep the research record. The goal is the best possible outcome, not the fastest completion. Make decisions yourself, document why, and keep going.
Context. Parallel teams are building a pocket finder and a docking predictor. This component supplies pocket fingerprints for similarity search and for docking ligands against pockets across the AlphaFold Protein Structure Database (~200M structures).

Docking: /cluster/work/beltrao/buhmanju/agentic_ai/workspaces/hackathon/autoresearch_docking
Pocket finder: /cluster/project/beltrao/gmagnus/pocket_detect
(FOR_FURTHER_DEVELOPMENT.md in pocket_detect might be useful)
Task. Design a method that scores the similarity of two protein binding pockets independent of sequence or fold, built on top of our existing fast pocket predictor. The intended use could go towards drug off-target prediction, drug repurposing, evolutionary comparison and or function annotation, but for this project we mostly want a versatile fast tool.
Treat pocket representation and comparison as an open design question. Look at literature and try to explore novel ideas. One idea that we find interesting is to use docking of a set of molecule fragments into a pocket as pocket descriptor (Fragment Based Drug Design). But please go down various paths as you see fit. 
We are also interested in pockets arising from protein protein interactions. We have included a dataset of high confidence predicted dimers. Please develop the method to work with pockets arising from PPIs. 
Datasets: If there are public benchmarks that are suited for the goal, please use those ones too. Only build your own one if needed, you can also use several. If you created a new benchmark dataset, split it into training, validation and a held-out test set before any modelling. You may use training and validation freely. You must not run any analysis on the held-out set until the final evaluation of your finished method. Make sure no test complex, or close homologue of one, leaks into training or into any model used to prepare receptors.
 you are running inside a Singularity container on the ETH Euler cluster
The container is the sandbox. Permission prompts are switched off. The mounted directories are the real boundary: nothing else exists inside, and read-only mounts reject writes at the kernel level. If a path you expect is missing, it was not mounted — say so.
No root. apt-get cannot install anything. Use uv, as a fallback use conda or pixi
Git: commit, do not push. There is no push credential. Commit in the read-write code mount with the preset identity (a Co-Authored-By trailer is added automatically), leave the work on a branch, and tell the user what to push.
Where to write. Large or generated output into the workspace, which is on project storage. Scratch into /tmp, which vanishes with the job

We have 4 rtx 4090s, 64 CPUs, and 192GB of RAM available for use. We also prefetched the AFDB and the PDB. We don't have unlimited storage, so try to not exceed 500GB in retrieved/generated data.

On euler has:
/cluster/work/beltrao/shared/alphafold/  - copy of the alphafold database
/cluster/scratch/jjaenes/pdb/  - copy of the PDB
/cluster/project/beltrao/gmagnus/dimers

Some things to look into for literature review:
ProSPECCTs, TOUGH-M1, TOUGH-C1, Vertex dataset, Kahraman dataset, Barelier dataset, sc-PDB, PLINDER, LIGYSIS, PoSSuM, ECIFP, KLIFS, GenomeScreenDB, ChEMBL co-target pairs, AlphaFold Database (AFDB), SiteEngine, G-LoSA, APoc, ProBiS, ProBiS-Fold, IsoMIF, KRIPO, FuzCav, Cavbase, SiteAlign, SiteMine, SiteContext, Siteomix, POEM subpocket similarity, metal binding site ICP alignment, Folddisco, pyScoMotif, ActSeek, ACP4, KiSSim, FUSED, SiteMatcher, DeeplyTough, Spherical CNN pocket classification, GraphSite, PocketAnchor, ProFSA, LEN-Seek, GTA-5, DMPPS, DrugCLIP pocket embeddings, PocketVec, LigUnity, BindCLIP, Simpatico, EPoCS, PocketScope, ErePOC, OneProt, Foldseek, MMseqs2, DataSAIL, CleanSplit, LP-PDBBind, HonestAffinity, pocket similarity data leakage, AlphaFold vs apo vs holo pocket robustness

We will come back and revisit progress in 24 hours so please aim to work within that time budget.

Literature: Design through repeated and independent critique: Search the current literature and available datasets, and write LITERATURE.md. Then draft DESIGN.md. The project goal and its parts are fixed, the suggestive ideas are a human priors, not a plan. Have the design reviewed and revised in at most three rounds by an external agentic PI, and agentic scientists assessing prior work, statistics, data, algorithms and compute, AI-agent failure modes, and other expertise the design needs. Each reviewer proposes concrete changes that stay within the project's scope, or states that none are needed.

Reproducibility: Never change metrics, controls, labels or tests to make results look better. Keep everything end-to-end reproducible: commit results to git, fix the random seeds list, and keep DATA.md listing the source, version, checksum and license of each dataset. Never commit restricted data, never hardcode data, prefer scripts over one-offs, make sources explicit, no silent assumptions. Don't trust a result until it has been checked. Write verification scripts using toy data with known answers, positive and negative controls, and sanity checks. An agent that didn't produce a result reviews it before you rely on it.

Research tree: Save this prompt verbatim to `PROMPT.md`. Keep track of the research in a research tree (RESEARCH_TREE.md), using a status legend: [ ] planned · [~] in progress · [x] done · [-] abandoned/negative · [!] key finding. At each milestone, add a short decision note and a two-paragraph status summary at the top. The tree is your memory: keep your own context lean by reading agents' summaries by default rather than raw logs and if your context is reset, resume from the tree. 

AI lessons: Keep LESSONS.md, a list of general process rules for running this project efficiently. Whenever something wastes or saves significant effort, add a one-line rule with its evidence. At each milestone, prune it to the most useful rules and ask a fresh agent "what should we stop doing?" and "what worked well?". 

Auto-research: Your job is to build the best possible method. Report runtime alongside accuracy. Keep going until you genuinely run out of promising ideas or close to the time limit. Then write REPORT.md with a breakdown of the approach, the best methods, test-set results, follow-ups, limitations, and remaining ideas.
