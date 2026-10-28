# Sub-agent a76f3eff41e587d07 — PPI pockets, docking descriptors, leakage (?)

Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to 1,500 characters; assistant text is complete. Thinking blocks are included where stored as text.


### PI / user turn · 2026-10-27 17:30:09

You are helping write a literature review for a project building a fast protein binding-pocket SIMILARITY method (sequence/fold independent), for AlphaFold-DB scale search, drug off-target prediction, function annotation, and pockets at protein-protein interfaces (we have AFDB predicted homo/heterodimers). We have a fast GPU Vina-like docking engine (~0.1-0.2 s per ligand-pocket). Return a dense factual text report (no files). Load WebSearch/WebFetch via ToolSearch query "select:WebSearch,WebFetch"; bioRxiv MCP tools also exist (load via ToolSearch "bioRxiv"). Cover three topics:

(1) DOCKING-PROFILE / LIGAND-BASED POCKET DESCRIPTORS. PocketVec (Balboa et al., Nat Commun 2024?): exactly what ligand set (how many, which: lead-like molecules? fragments?), docking program (rDock?), how the descriptor is built (rank vectors?), runtime per pocket, benchmarks and numbers they report (e.g. on ProSPECCTs subsets / their own), human proteome scale result, code availability. Also earlier docking-profile ideas: "affinity fingerprints" (Kauvar 1995), "docking profile similarity" (e.g. Fukunishi?, "Protein-ligand interaction profile / docking score vectors"), "inverse docking fingerprints", IFP-based pocket comparison, FragFEATURE, fragment-based pocket descriptors (e.g. "fragment hotspot maps", FTMap probe-based consensus sites / FTSite, "FTMap probe clusters to compare binding sites", "Hotspots API"), MaSIF-ligand, SILCS FragMaps, GRID molecular interaction fields (BioGPS, IsoMIF uses probe MIFs). Whatever is known about how many fragments/probes are needed, robustness, and runtime. Also Simpatico / LigUnity / DrugCLIP style pocket-ligand co-embeddings as "ligand-space" pocket descriptors. Summarize lessons for a "dock N fragments, use score/pose profile as descriptor" approach.

(2) PPI-INTERFACE POCKETS: what is known about small-molecule pockets at protein-protein interfaces (iPPI-DB, 2P2Idb, TIMBAL, PPI hot spots, transient pockets, "druggable pockets at PPI interfaces" e.g. Fuller/ Wells, "inferring interface ligandability", molecular glue pockets at interfaces, interface pockets in AlphaFold-Multimer models e.g. papers analysing pockets in predicted complexes/ the "AFDB complexes" or "predicted human interactome pockets" papers 2023-2026), I2I-SiteEngine and PIFACE (interface comparison/clustering), MaSIF-search/MaSIF-site, PInet, interface-similarity methods (iAlign, PCalign, IS-score/iAlign by Gao & Skolnick), any benchmark for comparing interface pockets. How interface pockets differ from classic pockets (shallower, more hydrophobic, larger, flatter? cite).

(3) DATA LEAKAGE & ROBUSTNESS: homology/pocket-similarity leakage in learned pocket models — DeeplyTough (trained on TOUGH-M1 with sequence-split; leakage?), DrugCLIP (trained on PDBbind/BioLiP; tested on DUD-E/LIT-PCBA; leakage analyses), ProFSA, PDBbind leakage papers (LP-PDBBind, CleanSplit/Graber et al. 2025, "HonestAffinity" verify, DataSAIL), "pocket similarity data leakage" (e.g. papers showing test/train pocket similarity inflates results, Volkov et al. 2022 J Med Chem "On the frustration to predict binding affinities from protein-ligand structures with deep neural networks"?). AlphaFold vs apo vs holo pocket robustness: studies comparing pocket similarity/pocket detection/docking on AF2 models vs holo vs apo (e.g. Scardino et al. 2023, Karelina et al. 2023 eLife docking on AF models, Holcomb et al., "AlphaFold2 models are holo-like" papers, any study re-running ProSPECCTs/TOUGH-M1 on AF models, PocketVec AF results, "pocket similarity AlphaFold models apo holo"). Also note that ProSPECCTs D1.2/NMR subsets test conformational robustness.

Be strict: never invent numbers, DOIs, or URLs; mark anything unverified. Target ~2500-3500 words with a reference list (DOIs/URLs).


### PI / user turn · 2026-10-27 17:30:09

<system-reminder>
Your final report is delivered through SubagentHandback: when your work is complete, call SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step. Only a SubagentHandback call reaches your caller as your result; plain text you write at the end is not delivered. Do not also send the report with SendMessage: your caller would get it twice.
</system-reminder>


### PI / user turn · 2026-10-27 17:30:10

Your response above was stopped by a safety classifier — this is not a tool or API error. The rest of it was withheld, and tool calls in it that had not finished did not run. Do not produce that content again, even reworded.


**→ tool call `ToolSearch`** · 2026-10-27 17:30:16

```
{"query": "select:WebSearch,WebFetch", "max_results": 5}
```


**← tool result**

```
[non-text content]
[non-text content]
```


### Assistant · 2026-10-27 17:30:19

I'll research each topic with web searches, starting with PocketVec and docking-profile descriptors.


**→ tool call `WebSearch`** · 2026-10-27 17:30:20

```
{"query": "PocketVec ligand-based pocket descriptor Balboa Nature Communications 2024 rDock", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:21

```
{"query": "Fukunishi protein-ligand docking score vector similarity binding site comparison", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "Fukunishi protein-ligand docking score vector similarity binding site comparison"

Links: [{"title":"Site2Vec: a reference frame invariant algorithm for vector embedding of protein-ligand binding sites","url":"https://arxiv.org/pdf/2003.08149"},{"title":"PLIC: protein–ligand interaction clusters","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3998096/"},{"title":"PocketMatch: A new algorithm to compare binding sites in protein structures","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2639437/"},{"title":"drugdesign.unistra.fr","url":"https://drugdesign.unistra.fr/lab/publications/paper116.pdf"},{"title":"PoSSuM: a database of known and potential ligand-binding sites in proteins","url":"https://cbrc3.cbrc.pj.aist.go.jp/~tomii/research/research.html"},{"title":"20130118 Tomii","url":"https://cbrc3.cbrc.pj.aist.go.jp/ja/education/pdf/20130118-Tomii.pdf"},{"title":"Alignment-Free Ultra-High-Throughput Comparison of Druggable Protein−Ligand Binding Sites","url":"https://lab.drugdesign.unistra.fr/publications/2010_weill/"},{"title":"academic.oup.com","url":"https://academic.oup.com/nar/article/40/D1/D541/2903183"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/313615"},{"title":"Scoring ligand similarity in structure-based virtual screening","url":"https://profiles.wustl.edu/en/publications/scoring-ligand-similarity-in-structure-based-virtual-screening/"}]

The search didn't return any work by Fukunishi on docking scores or binding-s
… [1,513 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "PocketVec ligand-based pocket descriptor Balboa Nature Communications 2024 rDock"

Links: [{"title":"Comprehensive detection and characterization of human druggable pockets through novel binding site descriptors","url":"https://www.biorxiv.org/content/10.1101/2024.03.14.584971.full.pdf"},{"title":"Nature Communications (Sep 2024)","url":"https://doaj.org/article/8c11db43ff354f759520de8c28ea0279"},{"title":"memoir.icrea.cat","url":"https://memoir.icrea.cat/?p=5848"},{"title":"Characterization of druggable pockets in the human proteome","url":"https://www.icrea.cat/ca/impacte/divulgacio/resultats-destacats/910/characterization-of-druggable-pockets-in-the-human-proteome"},{"title":"Characterization of druggable pockets in the human proteome","url":"https://www.icrea.cat/es/impacto/outreach/resultados-destacados/910/characterization-of-druggable-pockets-in-the-human-proteome"},{"title":"characterization of druggable pockets in the human proteome","url":"https://memoir.icrea.cat/2024/scientific-highlights/characterization-of-druggable-pockets-in-the-human-proteome/"},{"title":"Characterization of druggable pockets in the human proteome","url":"https://icrea.cat/impact/outreach/scientific-highlights/910/characterization-of-druggable-pockets-in-the-human-proteome"},{"title":"new computational tool identifies more 32000 points pharmacological interest human","url":"https://www.irbbarcelona.org/en/news/scientific/new-computational-tool-identifies-more-32
… [1,931 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:30:33

```
{"url": "https://www.nature.com/articles/s41467-024-52146-3", "prompt": "Extract exact methodological details of PocketVec: how many ligands/molecules are docked, what kind (lead-like? fragments?), which library they come from, which docking program(s), how the descriptor vector is built (ranks?), descriptor dimensionality, runtime per pocket, benchmarks used (ProSPECCTs subsets and performance numbers, AUC values), comparison to other pocket comparison methods, human proteome scale results (number of pockets, proteins, AlphaFold models), code availability URL, and any results about AlphaFold vs experimental structures."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:34

```
{"query": "Kauvar 1995 affinity fingerprinting protein binding site \"affinity fingerprint\" Chemistry Biology", "mode": "standard"}
```


**← tool result**

```
REDIRECT DETECTED: The URL redirects to a location that was not fetched automatically.

    Original URL: https://www.nature.com/articles/s41467-024-52146-3
    Redirect URL (from the server's Location header — server-supplied, not verified): https://idp.nature.com/authorize?response_type=cookie&client_id=grover&redirect_uri=https%3A%2F%2Fwww.nature.com%2Farticles%2Fs41467-024-52146-3
    Status: 303 See Other

    To complete your request, I need to fetch content from the redirected URL. Please use WebFetch again with these parameters:
    - url: "https://idp.nature.com/authorize?response_type=cookie&client_id=grover&redirect_uri=https%3A%2F%2Fwww.nature.com%2Farticles%2Fs41467-024-52146-3"
    - prompt: "Extract exact methodological details of PocketVec: how many ligands/molecules are docked, what kind (lead-like? fragments?), which library they come from, which docking program(s), how the descriptor vector is built (ranks?), descriptor dimensionality, runtime per pocket, benchmarks used (ProSPECCTs subsets and performance numbers, AUC values), comparison to other pocket comparison methods, human proteome scale results (number of pockets, proteins, AlphaFold models), code availability URL, and any results about AlphaFold vs experimental structures."
```


**← tool result**

```
Web search results for query: "Kauvar 1995 affinity fingerprinting protein binding site "affinity fingerprint" Chemistry Biology"

Links: [{"title":"Relating the shape of protein binding sites to binding affinity profiles: is there an association?","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2972294/"},{"title":"Predicting ligand binding to proteins by affinity fingerprinting (Q30428916)","url":"https://wikidp.org/Q30428916"},{"title":"bmcstructbiol.biomedcentral.com","url":"https://bmcstructbiol.biomedcentral.com/track/pdf/10.1186/1472-6807-10-32"},{"title":"A novel approach to quantitative chemical classification proves useful in drug discovery","url":"https://www.nature.com/articles/nbt0995-965"},{"title":"Alignment-Free Ultra-High-Throughput Comparison of Druggable Protein−Ligand Binding Sites","url":"https://lab.drugdesign.unistra.fr/publications/2010_weill/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3098077/figure/F1"},{"title":"Loading [a11y]/accessibility-menu.js","url":"https://unpaywall.org/10.1109%2FIV.2003.1217972"},{"title":"A simple and fuzzy method to align and compare druggable ligand-binding sites","url":"https://lab.drugdesign.unistra.fr/publications/2008_schalon/"},{"title":"data.epo.org","url":"https://data.epo.org/publication-server/rest/v1.2/publication-dates/19991215/patents/EP0411503NWB1/document.html"},{"title":"drugdesign.unistra.fr","url":"https://drugdesign.unistra.fr/lab/publications/paper116.pdf"}]


… [1,709 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:30:44

```
{"url": "https://www.biorxiv.org/content/10.1101/2024.03.14.584971v1.full", "prompt": "Extract exact methodological details of PocketVec: how many ligands/molecules are docked, what kind (lead-like? fragments?), which library, which docking program(s), how the descriptor vector is built (ranks?), descriptor dimensionality, runtime per pocket, benchmarks used (ProSPECCTs subsets and performance numbers, AUC values), comparison to other pocket comparison methods, human proteome scale results (numbers of pockets, proteins, AlphaFold models), code availability URL, and results about AlphaFold vs experimental/holo structures."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:45

```
{"query": "PocketVec ProSPECCTs AUC 128 lead-like molecules rDock descriptor benchmark results", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "PocketVec ProSPECCTs AUC 128 lead-like molecules rDock descriptor benchmark results"

Links: [{"title":"OneProt: Towards Multi-Modal Protein Foundation Models","url":"https://arxiv.org/pdf/2411.04863"},{"title":"Site2Vec: a reference frame invariant algorithm for vector embedding of protein-ligand binding sites","url":"https://arxiv.org/pdf/2003.08149"},{"title":"Comprehensive detection and characterization of human druggable pockets through novel binding site descriptors","url":"https://www.biorxiv.org/content/10.1101/2024.03.14.584971.full.pdf"},{"title":"IDEAS home Printed from https://ideas.repec.org/a/nat/natcom/v15y2024i1d10.1038_s41467-024-52146-3.html","url":"https://ideas.repec.org/a/nat/natcom/v15y2024i1d10.1038_s41467-024-52146-3.html"},{"title":"Characterization of druggable pockets in the human proteome","url":"https://www.icrea.cat/impact/outreach/scientific-highlights/910/characterization-of-druggable-pockets-in-the-human-proteome/"},{"title":"Characterization of druggable pockets in the human proteome","url":"https://www.icrea.cat/ca/impacte/divulgacio/resultats-destacats/910/characterization-of-druggable-pockets-in-the-human-proteome"},{"title":"Characterization of druggable pockets in the human proteome","url":"https://www.icrea.cat/es/impacto/outreach/resultados-destacados/910/characterization-of-druggable-pockets-in-the-human-proteome"},{"title":"Nature Communications (Sep 2024)","url":"https://doaj.org/article/8c11db43ff354f
… [2,270 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
**Descriptor construction**
- **Compounds:** The standard pipeline docks 128 lead-like molecules (LLM). These were chosen by Shannon entropy from a starting set of 1,000 LLM (MOE v2019.01, MW 200-450 g/mol). That 1,000-molecule set was built by k-means clustering (TAT fingerprints) of 650k lead-like molecules. A 667-compound Glide fragment set (MW 50-200) was tested but performed worse.
- **Docking:** rDock rigid docking with standard parameters, a 12 Å binding-site box, 25 runs, and DIHEDRAL_MODE FIXED. The score is the minimum SCORE.INTER. SMINA flexible docking was tested but rDock with LLM performed best.
- **Vector:** Docking scores are converted to ranks (SciPy rankdata, method max), with the best score ranked 1. Molecules with positive scores are outliers and get ranks 129, 130, or 131 (for scores 0-50, 50-100, and >100). Pockets are compared by cosine distance, and a distance of 0.17 is the similarity threshold.
- **Dimensionality:** 128 per pocket in the standard pipeline.
- **Runtime:** About 1 hour per pocket on an Intel Xeon Gold 6138 CPU.

**Benchmarks (ProSPECCTs, AUROC)**
- P1: 0.97; P1.2: 1.00; P2: 0.96; P3: 0.67; P4: 0.72; P5: 0.64; P7: 0.87.
- P6 and P6.2 were excluded.
- Weighted average of 0.89, second-best overall. The top method is SiteAlign, which is alignment-dependent and does not give a per-pocket descriptor.
- PocketVec beat the median and average in all datasets except P3.
- The paper says other descriptor methods (e.g., KRIPO, TIFP, DeeplyTough, B
… [2,426 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:31:08

```
{"url": "https://www.biorxiv.org/content/10.1101/2024.03.14.584971v1.full", "prompt": "Report on: effect of the number of docked molecules (10 vs 128 vs 1000) on ProSPECCTs AUROC; runtime/computational cost statements; parallelisation; comparison table of PocketVec against other methods per ProSPECCTs dataset; anything about PPI/interface pockets; limitations discussed; AlphaFold model robustness experiments.", "offset": 100000}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:09

```
{"query": "FragFEATURE fragment-based binding site prediction knowledge base Tang Altman", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "FragFEATURE fragment-based binding site prediction knowledge base Tang Altman"

Links: [{"title":"Knowledge-based Fragment Binding Prediction","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3998881/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3998881"},{"title":"Identification of binding pockets in protein structures using a knowledge-based potential derived from local structural similarities","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3434446/"},{"title":"PLoS Computational Biology (Apr 2014)","url":"https://doaj.org/article/f5f13f86fd164876ab8053b1c99e4bff"},{"title":"techfinder.stanford.edu","url":"https://techfinder.stanford.edu/print/pdf/node/30182"},{"title":"frag feature","url":"https://simtk.org/home/frag-feature/"},{"title":"Docket #: S14-069","url":"https://techfinder.stanford.edu/technology/fragfeature-knowledge-based-fragment-binding-prediction-using-unsupervised-machine"},{"title":"cs229.stanford.edu","url":"https://cs229.stanford.edu/proj2014/Flynn%20Wu,Predicting%20Protein%20Fragment%20Binding.pdf"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2881410"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC8243409"}]

FragFEATURE is a knowledge-based fragment binding predictor from Grace Tang and Russ Altman, published in PLOS Computational Biology in April 2014 (DOI 10.1371/journal.pcbi.1003589).

- **Knowledge base:**
… [1,301 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
This excerpt does not contain most of the requested material. It is a partial section (it starts 100,000 characters into the page) covering pocket-set construction, pocket comparison, and kinase profiling methods.

**Not covered in this excerpt:**
- **Effect of docked molecule count (10 vs 128 vs 1000) on ProSPECCTs AUROC:** No docking-count experiments or AUROC results appear.
- **Runtime and computational cost:** No statements are made.
- **Parallelisation:** Not mentioned.
- **Comparison table against other methods per ProSPECCTs dataset:** No table or ProSPECCTs results appear.
- **PPI or interface pockets:** Not discussed.
- **Limitations:** No limitations section appears.
- **AlphaFold model robustness experiments:** Not included. The excerpt only states that AF2-predicted pockets were filtered to exclude residues with pLDDT below 70.

**What the excerpt does cover:**
- **PDB-PD set:** Fpocket was run on apo PDB domain structures, pockets were ranked with Prank, and the top two per domain were kept. This gave 14,413 pockets in 7,403 domains.
- **AF2-PD set:** The same approach was applied to AlphaFold2 domain models, yielding 32,202 pockets in 19,211 domains.
- **Pocket properties:** Volume was computed with rDock and buriedness with BioPython.
- **Pocket comparisons:** Pairs were compared by PocketVec similarity, sequence identity, and Cα RMSD, with sequence alignment coverage of at least 80% and centroid distance under 6.14 Å.
- **Kinase inhibition analysis:** Binding
… [328 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:31:23

```
{"url": "https://www.biorxiv.org/content/10.1101/2024.03.14.584971v1.full", "prompt": "Find text about: (a) how AUROC varies with the number of predefined compounds docked (10, 128, 1000 lead-like molecules) and why 128 was chosen; (b) comparison of fragments (Glide fragment library, 667 compounds) vs lead-like molecules; (c) rDock rigid vs SMINA flexible docking comparison; (d) computational cost / CPU hours statements. Quote the relevant sentences.", "offset": 20000}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:24

```
{"query": "FTMap computational solvent mapping probe clusters compare binding sites hot spots Kozakov Vajda", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "FTMap computational solvent mapping probe clusters compare binding sites hot spots Kozakov Vajda"

Links: [{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3526383/"},{"title":"par.nsf.gov","url":"https://par.nsf.gov/servlets/purl/10343415"},{"title":"journals.iucr.org","url":"https://journals.iucr.org/d/issues/2022/06/00/qg5007/qg5007.pdf"},{"title":"hot spot analysis for driving the development of hits into leads","url":"https://researchconnect.stonybrook.edu/en/publications/hot-spot-analysis-for-driving-the-development-of-hits-into-leads-/"},{"title":"Development and applications of fragment based drug design methods","url":"https://www.bu.edu/bmerc/?p=226"},{"title":"oncotarget.com","url":"https://oncotarget.com/article/4968/pdf"},{"title":"research papers\\(\\def\\hfill{\\hskip 5em}\\def\\hfil{\\hskip 3em}\\def\\eqno#1{\\hfil {#1}}\\)","url":"https://journals.iucr.org/d/issues/2022/06/00/qg5007/"},{"title":"expanding ftmap for fragment based identification of pharmacophor","url":"https://researchconnect.stonybrook.edu/en/publications/expanding-ftmap-for-fragment-based-identification-of-pharmacophor/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3634182"},{"title":"expanding ftmap for fragment based identification of pharmacophor","url":"https://researchconnect.suny.edu/en/publications/expanding-ftmap-for-fragment-based-identification-of-pharmacophor/"}]

The search turned up
… [2,241 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
**(a) AUROC vs. number of docked compounds, and why 128 was chosen**

- The 128-compound set was chosen to be compact: "performances obtained in ProSPECCTs datasets by the 128 most diverse molecules were fairly similar to the original ones."
- Reducing the set "enabled a shorter length of the descriptor" and "alleviated the overall computational cost of the methodology."
- The authors also note that "the use of ∼100-200 molecules was often sufficient to get competitive performances in most datasets."
- The text gives no AUROC values for the 10-compound set. Fig 1b shows the 10, 128, and 1,000 comparisons, but the results are only described in the figure.

**(b) Fragments vs. lead-like molecules (LLM)**

- Outlier rankings "were rare with fragments but more frequent when using LLM."
- "The use of LLM and rDock rigid docking provided better results than other combinations."
- "LLM showed a superior discriminative power with respect to the size of the pocket."
- "LLM occupied a larger fraction of the binding sites than fragments."

**(c) rDock (rigid) vs. SMINA (flexible) docking**

- The two tools were used "to run rigid and flexible docking calculations, respectively, under the default parameters."
- "The use of rDock and LLM (128) was still the best strategy according to the ProSPECCTs datasets."
- The combination was adopted as "the standard and optimal methodology" for PocketVec descriptors.

**(d) Computational cost**

- "On average, the generation of a PocketVec descripto
… [508 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:40

```
{"query": "\"fragment hotspot maps\" Radoux Blundell hotspots API druggability GRID probes", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:41

```
{"query": "IsoMIF molecular interaction field binding site comparison Chartier Najmanovich", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "IsoMIF molecular interaction field binding site comparison Chartier Najmanovich"

Links: [{"title":"IsoMIF Finder: online detection of binding site molecular interaction field similarities","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4743630/"},{"title":"Papers: 10.1093/bioinformatics/btv616","url":"https://papers.ecosyste.ms/papers/10.1093%2Fbioinformatics%2Fbtv616"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC4743630"},{"title":"gabarit soutenance de these 2016 mc 1","url":"https://www.usherbrooke.ca/dep-biochimie-genomique/typo3temp/gabarit_soutenance_de_these_2016_mc-1.pdf"},{"title":"dblp.uni-trier.de","url":"https://dblp.uni-trier.de/pid/05/11478.html"},{"title":"nrg-qt.readthedocs.io","url":"https://nrg-qt.readthedocs.io/en/latest/software_description/IsoMIF.html"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3324516"},{"title":"research.unipg.it","url":"https://research.unipg.it/handle/11391/1238697"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2913663"},{"title":"scielo.br","url":"https://scielo.br/j/jbchs/a/GTP4ByjnyXS3J4WnPcc8cSF/?lang=en"}]

The search turned up the main IsoMIF papers, mostly the 2015 work by Matthieu Chartier and Rafael Najmanovich and the follow-up IsoMIF Finder web server.

- **Core method:** IsoMIF uses six probes and a coarse-grained force field to map interaction fields in cavities, then applies gr
… [1,250 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: ""fragment hotspot maps" Radoux Blundell hotspots API druggability GRID probes"

Links: [{"title":"www.ccdc.cam.ac.uk","url":"https://www.ccdc.cam.ac.uk/media/Documentation/11CB888E-FCAA-4C88-AA95-678AA1DDF4B8/11cb888efcaa4c88aa95678aa1ddf4b8.pdf"},{"title":"ndm.medsci.ox.ac.uk","url":"https://ndm.medsci.ox.ac.uk/publications/1099402"},{"title":"www.ndm.ox.ac.uk","url":"https://www.ndm.ox.ac.uk/publications/1099402/modal"},{"title":"2020 JCIM 1911","url":"https://www-spring.ch.cam.ac.uk/publications/pdf/2020_JCIM_1911.pdf"},{"title":"Researchers show how hotspot maps can detect structures contributing to compounds’ selectivity","url":"https://www.azolifesciences.com/news/20220304/Researchers-show-how-hotspot-maps-can-detect-structures-contributing-to-compoundse28099-selectivity.aspx"},{"title":"What are Hotspots in Structural Biology?","url":"https://www.blopig.com/blog/?p=5220"},{"title":"Mihaela Smilova Abstract","url":"https://cisrg.shef.ac.uk/shef2019/?p=250"},{"title":"www.ccdc.cam.ac.uk","url":"https://www.ccdc.cam.ac.uk/media/Documentation/A31F21C2-FC2C-4AA6-88F4-70E497EF7263/a31f21c2fc2c4aa688f470e497ef7263.pdf"},{"title":"Sample records for mapping interaction sites","url":"https://www.science.gov/topicpages/m/mapping+interaction+sites"},{"title":"“Hotspot mapping” accelerates early-phase drug design","url":"https://ccdc.cam.ac.uk/News/List/Hotspot-mapping-for-compound-selectivity-across-protein-families-in-drug-discovery"}]

Fragment Ho
… [1,997 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:52

```
{"query": "MaSIF Gainza Correia 2020 molecular surface fingerprints MaSIF-ligand pocket ligand type classification accuracy", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:53

```
{"query": "DrugCLIP contrastive pocket ligand NeurIPS 2023 DUD-E LIT-PCBA data leakage criticism", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "MaSIF Gainza Correia 2020 molecular surface fingerprints MaSIF-ligand pocket ligand type classification accuracy"

Links: [{"title":"MaSIF paper SS2025","url":"https://www-cbi.cs.uni-saarland.de/wp-content/uploads/2025/03/MaSIF-paper_SS2025.pdf"},{"title":"folia.unifr.ch","url":"https://folia.unifr.ch/global/documents/69770"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/606202.full.pdf"},{"title":"sonar.ch","url":"https://sonar.ch/global/documents/69770"},{"title":"MaSIF - Deciphering interaction fingerprints from protein molecular surfaces","url":"https://www.doi.org/10.5281/ZENODO.2625420"},{"title":"Deciphering interaction fingerprints from protein molecular surfaces using geometric deep learning","url":"https://research.uniroma1.it/en/node/53911"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/node/578352"},{"title":"当前位置: X-MOL 学术Nat. Methods › 论文详情","url":"https://www.x-mol.com/paper/5997631"},{"title":"69fb17e0 3cfe 404a 8002 06d77e1c5809","url":"https://infoscience.epfl.ch/signposting/describedby/69fb17e0-3cfe-404a-8002-06d77e1c5809"},{"title":"infoscience.epfl.ch","url":"https://infoscience.epfl.ch/record/273279?ln=en"}]

The search confirmed the basic framework but did not return the ligand classification accuracy figures.

- **Publication:** Gainza et al. published MaSIF in Nature Methods (ISSN 1548-7091), with the title "Deciphering interaction fingerprints from protein molecular surfaces using
… [946 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "DrugCLIP contrastive pocket ligand NeurIPS 2023 DUD-E LIT-PCBA data leakage criticism"

Links: [{"title":"Hidden bias in the DUD-E dataset leads to misleading performance of deep learning in structure-based virtual screening","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6701836/"},{"title":"Data Leakage and Redundancy in the LIT-PCBA Benchmark","url":"https://arxiv.org/pdf/2507.21404"},{"title":"Data Leakage and Redundancy in the LIT-PCBA Benchmark","url":"https://arxiv.org/html/2507.21404v2"},{"title":"Data Leakage and Redundancy in the LIT-PCBA Benchmark","url":"https://arxiv.org/html/2507.21404v1"},{"title":"arxiv.org","url":"https://arxiv.org/html/2310.06367v1"},{"title":"www.emergentmind.com","url":"https://www.emergentmind.com/papers/2507.21404"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2507.21404v2"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/2507.21404v2.pdf"},{"title":"Hidden Bias in the DUD-E Dataset Leads to Misleading Performance of Deep Learning in Structure-Based Virtual Screening","url":"https://chemrxiv.org/engage/chemrxiv/article-details/60c740eb702a9b200e18a196"},{"title":"cnn dud e","url":"https://simtk.org/projects/cnn-dud-e"}]

The search turned up two relevant lines of criticism, but nothing that directly audits DrugCLIP's own training data.

- **DrugCLIP itself:** The original paper frames virtual screening as dense retrieval, using contrastive learning to align pocket and molecule encoders. It repor
… [1,216 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:02

```
{"query": "2P2Idb iPPI-DB TIMBAL protein-protein interaction inhibitor database interface pocket properties", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:03

```
{"query": "pockets at protein-protein interfaces AlphaFold-Multimer predicted complexes druggable interface pockets proteome-wide 2024 2025", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "2P2Idb iPPI-DB TIMBAL protein-protein interaction inhibitor database interface pocket properties"

Links: [{"title":"pubs.rsc.org","url":"https://pubs.rsc.org/en/content/getauthorversionpdf/c4md00328d"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC4792518"},{"title":"PLoS ONE (Mar 2010)","url":"https://doaj.org/article/842ecb5261c34fba9354aefea85ef29b"},{"title":"IDEAS home Printed from https://ideas.repec.org/a/plo/pone00/0009598.html","url":"https://ideas.repec.org/a/plo/pone00/0009598.html"},{"title":"academic.oupdev.silverchair.com","url":"https://academic.oupdev.silverchair.com/database/article/2630150"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3531195"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2834754"},{"title":"Rational design of protein–protein interaction inhibitors","url":"https://pubs.rsc.org/en/content/articlehtml/2015/md/c4md00328d"},{"title":"2p2idb main","url":"https://2p2idb.marseille.inserm.fr/php/2p2idb_main.php"},{"title":"2p2idb main","url":"https://dart.marseille.inserm.fr/php/2p2idb_main.php"}]

Here's a summary of the search results on the three PPI inhibitor databases.

**2P2Idb** is a structural database. It covers protein-protein complexes where both the protein pair and a protein-inhibitor complex have been solved structurally, and it focuses on orthosteric inhibitors that compete directly at the interface.
… [1,631 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "pockets at protein-protein interfaces AlphaFold-Multimer predicted complexes druggable interface pockets proteome-wide 2024 2025"

Links: [{"title":"Flexibility and small pockets at protein–protein interfaces: New insights into druggability","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4726663/"},{"title":"Structural landscapes of PPI interfaces","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9294409/"},{"title":"academiccommons.columbia.edu","url":"https://academiccommons.columbia.edu/doi/10.7916/8qes-qr75/download"},{"title":"Theses Doctoral","url":"https://academiccommons.columbia.edu/doi/10.7916/gnd3-mf07"},{"title":"memoir.icrea.cat","url":"https://memoir.icrea.cat/?p=5848"},{"title":"characterization of druggable pockets in the human proteome","url":"https://memoir.icrea.cat/2024/scientific-highlights/characterization-of-druggable-pockets-in-the-human-proteome/"},{"title":"IDEAS home Printed from https://ideas.repec.org/a/nat/natcom/v15y2024i1d10.1038_s41467-024-52146-3.html","url":"https://ideas.repec.org/a/nat/natcom/v15y2024i1d10.1038_s41467-024-52146-3.html"},{"title":"Nature Communications (Sep 2024)","url":"https://doaj.org/article/8c11db43ff354f759520de8c28ea0279"},{"title":"Journal article","url":"https://findanexpert.unimelb.edu.au/scholarlywork/1110999-flexibility-and-small-pockets-at-protein-protein-interfaces--new-insights-into-druggability"},{"title":"walter.hms.harvard.edu","url":"https://walter.hms.harvard.edu/wp
… [1,871 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:14

```
{"query": "iAlign IS-score Gao Skolnick protein-protein interface structure comparison PCalign benchmark", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:15

```
{"query": "PIFACE interface clustering Keskin Nussinov nonredundant interface structures I2I-SiteEngine", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "iAlign IS-score Gao Skolnick protein-protein interface structure comparison PCalign benchmark"

Links: [{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3076516"},{"title":"ialign a method for the structural comparison of protein protein","url":"https://portal.fis.tum.de/en/publications/ialign-a-method-for-the-structural-comparison-of-protein-protein-/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2935406"},{"title":"fh-zwickau.de","url":"https://www.katalog.fh-zwickau.de/Record/ai-49-aHR0cDovL2R4LmRvaS5vcmcvMTAuMTA5My9iaW9pbmZvcm1hdGljcy9idHE0MDQ/Description"},{"title":"ialign 8py source","url":"https://openstructure.org/doxygen/2.8/de/d83/ialign_8py_source.html"},{"title":"ialign 8py source","url":"https://openstructure.org/doxygen/2.6/de/d83/ialign_8py_source.html"},{"title":"Comparing PPIs","url":"https://ppiref.readthedocs.io/en/latest/comparing_ppis.html"},{"title":"Eintrag weiter verarbeiten","url":"https://www.katalog.fh-zwickau.de/Record/ai-49-aHR0cDovL2R4LmRvaS5vcmcvMTAuMTA5My9iaW9pbmZvcm1hdGljcy9idHE0MDQ/Details"},{"title":"Center for the Study of Systems Biology","url":"https://sites.gatech.edu/cssb/ialign"},{"title":"ialign 8py source","url":"https://www.openstructure.org/doxygen/dev/de/d83/ialign_8py_source.html"}]

The search turned up solid material on iAlign and the IS-score, but nothing on PCalign or a PCalign benchmark.

- **IS-score origin:** Gao and Skolnick 
… [1,577 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "PIFACE interface clustering Keskin Nussinov nonredundant interface structures I2I-SiteEngine"

Links: [{"title":"Non-Redundant Unique Interface Structures as Templates for Modeling Protein Interactions","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3903793/"},{"title":"Publication: Non-redundant unique interface structures as templates for modeling protein interactions","url":"https://research.hub.ku.edu.tr/entities/publication/ba8250ea-c9ac-4145-8cb2-2dfa91c70ccd/full"},{"title":"Database Commons","url":"https://ngdc.cncb.ac.cn/databasecommons/database/id/4990"},{"title":"ba8250ea c9ac 4145 8cb2 2dfa91c70ccd","url":"https://research.hub.ku.edu.tr/entities/publication/ba8250ea-c9ac-4145-8cb2-2dfa91c70ccd"},{"title":"ncifrederick.cancer.gov","url":"https://ncifrederick.cancer.gov/scientificlibrary/publication/Approved.aspx?Id=4675"},{"title":"Publication: A new, structurally nonredundant, diverse data set of protein-protein interfaces and its implications","url":"https://research.hub.ku.edu.tr/entities/publication/ff3c93ee-77b6-4797-bbc7-e9e1258ebf85/full"},{"title":"a new structurally nonredundant diverse data set of protein prote","url":"https://cris.tau.ac.il/en/publications/a-new-structurally-nonredundant-diverse-data-set-of-protein-prote/"},{"title":"pubmed.ncbi.nlm.nih.gov","url":"https://pubmed.ncbi.nlm.nih.gov/15980484"},{"title":"ncifrederick.cancer.gov","url":"https://ncifrederick.cancer.gov/scientificlibrary/publication/Approved.
… [1,605 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:26

```
{"query": "DeeplyTough learning structural search binding sites TOUGH-M1 Vert ProSPECCTs sequence split leakage", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:27

```
{"query": "CleanSplit PDBbind data leakage Graber 2025 binding affinity prediction similarity splits", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "CleanSplit PDBbind data leakage Graber 2025 binding affinity prediction similarity splits"

Links: [{"title":"Resolving data bias improves generalization in binding affinity prediction","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12552120/"},{"title":"GEMS – Enhancing Generalizable Binding Affinity Prediction by Removing Data Leakage and Integrating Language Model Embeddings into Graph Neural Networks","url":"https://www.biorxiv.org/content/10.1101/2024.12.09.627482.full.pdf"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2024.12.09.627482v2"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/2308.09639v3"},{"title":"www.arxiv.org","url":"https://www.arxiv.org/pdf/2308.09639"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC9850481"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2308.09639v2"},{"title":"Improving generalisability of 3D binding affinity models in low data regimes","url":"https://arxiv.org/html/2409.12995v1"},{"title":"Leak Proof PDBBind: A Reorganized Dataset of Protein-Ligand Complexes for More Generalizable Binding Affinity Prediction","url":"https://arxiv.org/html/2308.09639v2"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2409.12995v1"}]

The search turned up a 2025 paper by Graber and colleagues, first posted as the GEMS preprint, that introduces PDBbind CleanSplit. I couldn't confirm the exact 2025 publication details beyond the matching title, so 
… [1,135 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "DeeplyTough learning structural search binding sites TOUGH-M1 Vert ProSPECCTs sequence split leakage"

Links: [{"title":"DeepSurf: A surface-based deep learning approach for the prediction of ligand binding sites on proteins","url":"https://arxiv.org/pdf/2002.05643"},{"title":"Site2Vec: a reference frame invariant algorithm for vector embedding of protein-ligand binding sites","url":"https://arxiv.org/pdf/2003.08149"},{"title":"DeeplyTough: Learning Structural Comparison of Protein Binding Sites","url":"https://cs.paperswithcode.com/paper/deeplytough-learning-structural-comparison-of"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/node/500851"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/8"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/9"},{"title":"castjournals.cast.org.cn","url":"https://castjournals.cast.org.cn/joweb/research/EN/1154841531136725337"},{"title":"tough.forumbee.com","url":"https://tough.forumbee.com/t/x16qjh?r=k96qjs"},{"title":"how to model a leakage around existing well annulus in tough","url":"https://tough.forumbee.com/t/x16qjh/how-to-model-a-leakage-around-existing-well-annulus-in-tough"},{"title":"tough.forumbee.com","url":"https://tough.forumbee.com/t/x16qjh?r=h46ymm"}]

I ran one search. It did not find anything specifi
… [2,261 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:32:42

```
{"url": "https://arxiv.org/abs/2002.06369", "prompt": "Is this the DeeplyTough paper (Simonovsky & Meyers, Learning Structural Comparison of Protein Binding Sites)? If so, summarize: training data (TOUGH-M1), how train/test splits were made with respect to sequence identity, evaluation datasets (TOUGH-M1, Vertex, ProSPECCTs), reported AUC numbers, and any discussion of data leakage or generalization failure."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:43

```
{"query": "Volkov 2022 \"frustration to predict binding affinities\" deep neural networks protein-ligand structures J Med Chem", "mode": "standard"}
```


**← tool result**

```
No, this isn't the DeeplyTough paper. The page is arXiv:2002.06369, "Perfect Sampling of Hawkes Processes and Queues with Hawkes Arrivals" by Xinyun Chen (math.PR, 2020). It covers probability theory, not protein binding site comparison.

The abstract describes a perfect sampling algorithm for single-server queues with Hawkes arrivals and general i.i.d. service times. It assumes stability, a light-tailed excitation function, and a service-time moment generating function that is finite near the origin. It also proposes a more computationally efficient perfect sampling algorithm for Hawkes processes.

The page contains none of the items you asked about: TOUGH-M1, sequence-identity train/test splits, the Vertex or ProSPECCTs evaluation sets, AUC results, or any discussion of data leakage or generalization. To find the DeeplyTough paper, search for Simonovsky and Meyers' work on learning structural comparison of protein binding sites.
```


**← tool result**

```
Web search results for query: "Volkov 2022 "frustration to predict binding affinities" deep neural networks protein-ligand structures J Med Chem"

Links: [{"title":"The Impact of Data on Structure-Based Binding Affinity Predictions Using Deep Neural Networks","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10671244/"},{"title":"PIGNet2: A Versatile Deep Learning-based Protein-Ligand Interaction Prediction Model for Binding Affinity Scoring and Virtual Screening","url":"https://arxiv.org/pdf/2307.01066"},{"title":"Prediction of protein–ligand binding affinity via deep learning models","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10939342/"},{"title":"2022 volkov","url":"https://lab.drugdesign.unistra.fr/publications/2022_volkov/"},{"title":"lab.drugdesign.unistra.fr","url":"https://lab.drugdesign.unistra.fr/tags/proteins/metabolism"},{"title":"neural networks computer","url":"https://lab.drugdesign.unistra.fr/tags/neural-networks-computer/"},{"title":"turk j","url":"https://lab.drugdesign.unistra.fr/authors/turk-j."},{"title":"دورية أكاديمية","url":"https://nufind.nu.edu.sa/EdsRecord/cmedm,38722047"},{"title":"VOLKOV Mikhail 2023 ED222","url":"https://publication-theses.unistra.fr/public/theses_doctorat/2023/VOLKOV_Mikhail_2023_ED222.pdf"},{"title":"Citation sources","url":"https://peerj.com/articles/7362/citations"}]

The paper exists and matches your query. It is Volkov et al., "On the Frustration to Predict Binding Affinities from Protein-Ligand Structures with D
… [1,600 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:32:55

```
{"url": "https://pubs.acs.org/doi/10.1021/acs.jcim.0c00131", "prompt": "Is this DeeplyTough (Simonovsky & Meyers, JCIM 2020)? Summarize abstract: training set, how train/test split controlled for sequence identity, evaluation on TOUGH-M1, Vertex, ProSPECCTs, AUC values reported, and statements about generalization."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:57

```
{"query": "Karelina Terry Shoichet eLife 2023 \"How accurately can one predict drug binding modes using AlphaFold models\"", "mode": "standard"}
```


**← tool result**

```
The server returned HTTP 403 Forbidden.

The response body was not retrieved. If this URL requires authentication, use an authenticated tool (e.g. `gh` for GitHub, or an MCP-provided fetch tool) instead of WebFetch.
```


**← tool result**

```
Web search results for query: "Karelina Terry Shoichet eLife 2023 "How accurately can one predict drug binding modes using AlphaFold models""

Links: [{"title":"How accurately can one predict drug binding modes using AlphaFold models?","url":"https://www.biorxiv.org/content/10.1101/2023.05.18.541346.full.pdf"},{"title":"How accurately can one predict drug binding modes using AlphaFold models?","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10746139/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10746139"},{"title":"elifesciences.org","url":"https://elifesciences.org/articles/89386.pdf"},{"title":"How accurately can one predict drug binding modes using AlphaFold models?","url":"https://elifesciences.org/articles/89386"},{"title":"elifesciences.org","url":"https://elifesciences.org/reviewed-preprints/89386v1.pdf"},{"title":"How accurately can one predict drug binding modes using AlphaFold models?","url":"https://elifesciences.org/articles/89386v1"},{"title":"How accurately can one predict drug binding modes using AlphaFold models?","url":"https://elifesciences.org/reviewed-preprints/89386v1/reviews"},{"title":"How accurately can one predict drug binding modes using AlphaFold models?","url":"https://elifesciences.org/articles/89386/peer-reviews"},{"title":"DOI: 10.7554/elife.89386.2 ISSN: 2050-084X","url":"https://www.citedrive.com/en/discovery/how-accurately-can-one-predict-drug-binding-modes-using-alphafold-models/"}]

The paper is in t
… [896 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:33:05

```
{"query": "Scardino Cavalli Sanchez-Garcia 2023 \"How good are AlphaFold models for docking\" virtual screening performance iScience", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:33:06

```
{"query": "Holcomb Chang Dill \"evaluation of AlphaFold2 structures as docking targets\" Protein Science 2023", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "Holcomb Chang Dill "evaluation of AlphaFold2 structures as docking targets" Protein Science 2023"

Links: [{"title":"Benchmarking AlphaFold for protein complex modeling reveals accuracy determinants","url":"https://www.biorxiv.org/content/10.1101/2021.10.23.465575.full.pdf"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC9794023"},{"title":"Google Scholar: citations","url":"https://ddd.uab.cat/record/328496?ln=en"},{"title":"Google Scholar: citas","url":"https://ddd.uab.cat/record/328496?ln=es"},{"title":"Google Scholar: cites","url":"https://ddd.uab.cat/record/328496"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC12465486"},{"title":"evaluation of alphafold2 structures for hit identification across","url":"https://research.mpu.edu.mo/en/publications/evaluation-of-alphafold2-structures-for-hit-identification-across/"},{"title":"evaluation of alphafold2 structures for hit identification across","url":"https://research.mpu.edu.mo/zh/publications/evaluation-of-alphafold2-structures-for-hit-identification-across/"},{"title":"elifesciences.org","url":"https://elifesciences.org/reviewed-preprints/89386/reviews"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10769324"}]

The paper is in the search results. It is Holcomb, Chang, Goodsell, and Forli, "Evaluation of AlphaFold2 structures as docking targets," *Protein Science* 2023;32(1):e4530 (PMCID PMC97
… [890 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "Scardino Cavalli Sanchez-Garcia 2023 "How good are AlphaFold models for docking" virtual screening performance iScience"

Links: [{"title":"Are Deep Learning Structural Models Sufficiently Accurate for Virtual Screening? Application of Docking Algorithms to AlphaFold2 Predicted Structures","url":"https://www.biorxiv.org/content/10.1101/2022.08.18.504412.full.pdf"},{"title":"Reliability of AlphaFold2 Models in Virtual Drug Screening: A Focus on Selected Class A GPCRs","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11432040/"},{"title":"How good are AlphaFold models for docking-based virtual screening?","url":"https://chemrxiv.org/engage/chemrxiv/article-details/6316a14149042ab863cd0481"},{"title":"client.prod.orp.cambridge.org","url":"https://client.prod.orp.cambridge.org/engage/chemrxiv/article-details/6316a14149042ab863cd0481"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC12465486"},{"title":"are deep learning structural models sufficiently accurate","url":"https://bsc.es/ca/print/research-and-development/publications/are-deep-learning-structural-models-sufficiently-accurate"},{"title":"par.nsf.gov","url":"https://par.nsf.gov/servlets/purl/10527732"},{"title":"review report","url":"https://www.mdpi.com/1420-3049/29/22/5272/review_report"},{"title":"Google Scholar: citations","url":"https://ddd.uab.cat/record/328496?ln=en"},{"title":"Issue 5, 2026","url":"https://pubs.rsc.org/en/content/articlelanding/2026
… [1,824 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:33:19

```
{"query": "ProSPECCTs benchmark Ehrt Brinkjost Koch 2018 binding site comparison datasets NMR structures decoys evaluation", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:33:20

```
{"query": "Fuller Burgoyne Jackson \"predicting druggable binding sites at the protein-protein interface\" 2009 Drug Discovery Today", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "Fuller Burgoyne Jackson "predicting druggable binding sites at the protein-protein interface" 2009 Drug Discovery Today"

Links: [{"title":"Predicting where Small Molecules Bind at Protein-Protein Interfaces","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3591369/"},{"title":"Predicting binding sites of hydrolase-inhibitor complexes by combining several methods","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC544855/"},{"title":"Fuller thesis final","url":"https://etheses.whiterose.ac.uk/id/eprint/1699/1/Fuller_thesis_final.pdf"},{"title":"Open Access Article","url":"https://pubs.rsc.org/en/content/articlehtml/2011/mb/c0mb00200c"},{"title":"Publication: Hot spots in protein-protein interfaces: towards drug discovery","url":"https://research.hub.ku.edu.tr/entities/publication/6376d625-cb0d-469c-9b68-82216b2aa1ad/full"},{"title":"www.bu.edu","url":"https://www.bu.edu/bmerc/?p=93"},{"title":"pubs.rsc.org","url":"https://pubs.rsc.org/en/content/articlepdf/2011/mb/c0mb00200c"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3158149"},{"title":"White Rose University Consortium logo","url":"https://etheses.whiterose.ac.uk/1699"},{"title":"paper on druggability of protein protein interactions was featured in pnas and highlighted in nature reviews drug discovery","url":"https://www.bu.edu/bmerc/2011/11/01/paper-on-druggability-of-protein-protein-interactions-was-featured-in-pnas-and-highlighted-in-nature-reviews-d
… [1,351 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "ProSPECCTs benchmark Ehrt Brinkjost Koch 2018 binding site comparison datasets NMR structures decoys evaluation"

Links: [{"title":"A benchmark driven guide to binding site comparison: An exhaustive evaluation using tailor-made data sets (ProSPECCTs)","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6224041/"},{"title":"OneProt: Towards Multi-Modal Protein Foundation Models","url":"https://arxiv.org/pdf/2411.04863"},{"title":"A benchmark driven guide to binding site comparison: an exhaustive evaluation using tailor-made data sets (ProSPECCTs)","url":"https://eldorado.tu-dortmund.de/items/1e566b9f-6622-423f-813d-163cb81ff14b/full"},{"title":"Authors: Ehrt, Christiane","url":"https://eldorado.tu-dortmund.de/handle/2003/38106"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/pmid/30408032"},{"title":"eldorado.tu-dortmund.de","url":"https://eldorado.tu-dortmund.de:443/bitstream/2003/38106/1/journal.pcbi.1006483.pdf"},{"title":"Eintrag weiter verarbeiten","url":"https://katalog.hszg.de/Record/ai-49-aHR0cDovL2R4LmRvaS5vcmcvMTAuMTM3MS9qb3VybmFsLnBjYmkuMTAwNjQ4Mw/Details"},{"title":"A benchmark driven guide to binding site comparison: an exhaustive evaluation using tailor-made data sets (ProSPECCTs)","url":"https://eldorado.tu-dortmund.de/items/1e566b9f-6622-423f-813d-163cb81ff14b"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/60994216"},{"title":"DOI: 10.1002/ardp.202300661 ISSN: 0365-6233","url":"https://www.ci
… [1,830 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:33:33

```
{"query": "Eyrisch Helms transient pockets protein-protein interface molecular dynamics IL-2 Bcl-xL MDM2 2007", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:33:34

```
{"query": "Kozakov Vajda 2011 PNAS \"structural conservation of druggable hot spots in protein-protein interfaces\"", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "Kozakov Vajda 2011 PNAS "structural conservation of druggable hot spots in protein-protein interfaces""

Links: [{"title":"paper on druggability of protein protein interactions was featured in pnas and highlighted in nature reviews drug discovery","url":"https://www.bu.edu/bmerc/2011/11/01/paper-on-druggability-of-protein-protein-interactions-was-featured-in-pnas-and-highlighted-in-nature-reviews-drug-discovery"},{"title":"www.bu.edu","url":"https://www.bu.edu/bmerc/?p=93"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3158149"},{"title":"cdi proquest miscellaneous 899151969","url":"https://vufind.lboro.ac.uk/PrimoRecord/cdi_proquest_miscellaneous_899151969"},{"title":"research.hub.ku.edu.tr","url":"https://research.hub.ku.edu.tr/entities/publication/2956819d-884b-4c03-b7cf-2222d7a4bb3a/full"},{"title":"identification of druggable hot spots on proteins and in protein","url":"https://researchconnect.stonybrook.edu/en/publications/identification-of-druggable-hot-spots-on-proteins-and-in-protein-/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3245113/"},{"title":"From: chemistry-request at ccl.net","url":"https://server.ccl.net/cca/info/conferencelist/mess0015964.html"},{"title":"From: chemistry-request at ccl.net","url":"https://ccl.net/cca/info/conferencelist/mess0015964.html"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3623692"}]

The paper
… [1,619 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "Eyrisch Helms transient pockets protein-protein interface molecular dynamics IL-2 Bcl-xL MDM2 2007"

Links: [{"title":"Inhibition of Protein-Protein Interactions","url":"https://www-cbi.cs.uni-saarland.de/?p=305"},{"title":"Generic placeholder image","url":"https://benthamscience.com/article/45419"},{"title":"Generic placeholder image","url":"https://www.eurekaselect.com/article/45419"},{"title":"Please use this identifier to cite or link to this item:","url":"https://publikationen.sulb.uni-saarland.de/handle/20.500.11880/22667?locale=en"},{"title":"Please use this identifier to cite or link to this item:","url":"https://jahrbib.sulb.uni-saarland.de/handle/20.500.11880/22667?locale=en"},{"title":"- Poster presentation","url":"https://bmcchem.biomedcentral.com/articles/10.1186/1752-153X-2-S1-P34"},{"title":"EPOS-BP – Ensemble of Pockets on Protein Surfaces with BALLPass","url":"https://www-cbi.cs.uni-saarland.de/software/epos_bp-ensemble-of-pockets-on-protein-surfaces-with-ballpass/"},{"title":"EPOS manual","url":"https://www-cbi.cs.uni-saarland.de/wp-content/uploads/EPOS/EPOS-manual.pdf"},{"title":"EPOS-BP – Ensemble of Pockets on Protein Surfaces with BALLPass","url":"https://www-cbi.cs.uni-saarland.de/?p=2174"},{"title":"1752 153X 2 S1 P34","url":"https://biomedcentral-bmcchem.publicaciones.saludcastillayleon.es/articles/10.1186/1752-153X-2-S1-P34"}]

The search confirms the 2007 paper by Eyrisch and Helms in the Journal of Medicinal Chemistry
… [1,393 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:33:45

```
{"query": "ProFSA pocket pretraining fragment-surroundings alignment pocket representation learning ICLR 2024", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:33:46

```
{"query": "LigUnity unified protein-ligand model virtual screening lead optimization 2025 Nature", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "ProFSA pocket pretraining fragment-surroundings alignment pocket representation learning ICLR 2024"

Links: [{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://proceedings.iclr.cc/paper_files/paper/2024/hash/6cc31b44d88dce8380d36e81485cd07f-Abstract-Conference.html"},{"title":"iclr.cc","url":"https://ICLR.cc/virtual/2024/poster/17577"},{"title":"openreview.net","url":"https://openreview.net/pdf/fcb728a7e3b8f50b0b315d0afbd69ca490308c3e.pdf"},{"title":"License: arXiv.org perpetual non-exclusive license","url":"https://arxiv.org/html/2310.07229v2"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2310.07229v1"},{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://ar5iv.labs.arxiv.org/html/2310.07229"},{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://chatpaper.com/es/paper/7088"},{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://chatpaper.com/fr/paper/7088"},{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://chatpaper.com/de/paper/7088"},{"title":"self supervised pocket pretraining via","url":"https://sotaverified.org/papers/self-supervised-pocket-pretraining-via"}]

The paper is "Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment" (ProFSA), by Bowen Gao,
… [1,403 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "LigUnity unified protein-ligand model virtual screening lead optimization 2025 Nature"

Links: [{"title":"Generative Modeling in Protein Design: Neural Representations, Conditional Generation, and Evaluation Standards","url":"https://arxiv.org/pdf/2603.26378"},{"title":"Hierarchical affinity landscape navigation through learning a shared pocket-ligand space","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12546767/"},{"title":"Hierarchical affinity landscape navigation through learning a shared pocket-ligand space","url":"https://www.biorxiv.org/content/10.1101/2025.02.17.638554.full.pdf"},{"title":"Learning Protein-Ligand Binding in Hyperbolic Space","url":"https://arxiv.org/pdf/2508.15480"},{"title":"LigUnity / README.md","url":"https://huggingface.co/Irwiny/LigUnity/blob/main/README.md"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2025.02.17.638554v2"},{"title":"YAML Metadata Warning:empty or missing yaml metadata in repo card","url":"https://huggingface-gw-kz.just-ai.com/Irwiny/LigUnity"},{"title":"Please use this identifier to cite or link to this item:","url":"https://www.um.edu.mt/library/oar/handle/123456789/90090"},{"title":"ora.ox.ac.uk","url":"https://ora.ox.ac.uk/objects/uuid:0622aab5-e8b6-4c95-90b5-47b68e07c499/files/m8da2bf814c66665d3c77761f05d93a04"},{"title":"app.alphaneural.io","url":"https://app.alphaneural.io/assets/Irwiny/LigUnity"}]

I found no Nature-family publication for LigUnity. The mai
… [1,666 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:33:57

```
{"query": "SILCS site identification by ligand competitive saturation FragMaps MacKerell binding site comparison", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:33:58

```
{"query": "KRIPO subpocket fingerprint Ritschel TIFP triangle interaction fingerprint Desaphy Rognan binding site comparison", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "KRIPO subpocket fingerprint Ritschel TIFP triangle interaction fingerprint Desaphy Rognan binding site comparison"

Links: [{"title":"science.ecosyste.ms","url":"https://science.ecosyste.ms/projects/21323"},{"title":"Similar fragments","url":"https://nodepit.com/node/nl.esciencecenter.e3dchem.kripodb.ws.fragmentsbysimilarity.FragmentBySimilarityFactory"},{"title":"github.com","url":"https://github.com/3D-e-Chem/kripo"},{"title":"Published February 22, 2016","url":"https://zenodo.org/records/46403"},{"title":"Published March 24, 2016","url":"https://zenodo.org/records/48251"},{"title":"Published May 31, 2016","url":"https://zenodo.org/records/53891"},{"title":"Welcome to the kissim documentation","url":"https://kissim.readthedocs.io/"},{"title":"Published February 12, 2016","url":"https://zenodo.org/records/45990"},{"title":"zenodo.org","url":"https://zenodo.org/records/45907"},{"title":"Published March 24, 2016","url":"https://zenodo.org/records/48247"}]

The search turned up good coverage of KRIPO itself, but nothing on Desaphy and Rognan or a direct binding-site comparison against them.

- **What KRIPO is:** The software documentation describes KRIPO as a structure-based pharmacophore approach, with Tina Ritschel, Tom Schirris, and Frans Russel as the authors of the original paper. Its tooling is open source and maintained by the 3D-e-Chem group.
- **Subpockets and fingerprints:** The kripodb library defines a subpocket as the part of the prot
… [865 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "SILCS site identification by ligand competitive saturation FragMaps MacKerell binding site comparison"

Links: [{"title":"patents.google.com","url":"https://patents.google.com/patent/US10002228"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2700966"},{"title":"computational fragment based binding site identification by ligand competitive saturation","url":"https://kbbox.h-its.org/toolbox/examples/computational-fragment-based-binding-site-identification-by-ligand-competitive-saturation/"},{"title":"mackerell.umaryland.edu","url":"https://mackerell.umaryland.edu/research.shtml"},{"title":"posted on 2013-12-23, 00:00authored byE. Prabhu Raman, Wenbo Yu, Sirish K. Lakkaraju, Alexander D. MacKerell","url":"https://acs.figshare.com/articles/journal_contribution/Inclusion_of_Multiple_Fragment_Types_in_the_Site_Identification_by_Ligand_Competitive_Saturation_SILCS_Approach/2338468"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3490637"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3090225"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC4048638"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3947602"},{"title":"pubs.rsc.org","url":"https://pubs.rsc.org/en/content/articlepdf/2021/sc/d1sc01781k"}]

SILCS (Site Identification by Ligand Competitive Saturation) is a MacKerell lab method fo
… [2,152 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:11

```
{"query": "DataSAIL data splitting against information leakage Joeres Kalinin Kalinina 2025 Nature Communications", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:12

```
{"query": "\"AlphaFold2\" predicted structures resemble holo apo conformational state pocket side chains study", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "DataSAIL data splitting against information leakage Joeres Kalinin Kalinina 2025 Nature Communications"

Links: [{"title":"DataSAIL: Data Splitting Against Information Leakage","url":"https://www.biorxiv.org/content/10.1101/2023.11.15.566305.full.pdf"},{"title":"Data splitting to avoid information leakage with DataSAIL","url":"https://open.fau.de/handle/openfau/39023"},{"title":"Data splitting to avoid information leakage with DataSAIL","url":"https://open.fau.de/items/b52f001e-9775-4b3c-be10-a74a16e49edd/full"},{"title":"Data splitting to avoid information leakage with DataSAIL","url":"https://cris.fau.de/publications/340156472"},{"title":"Paper published in Nature Communications","url":"https://www.bionets.tf.fau.de/news/paper-published-in-nature-communications-2/"},{"title":"Data splitting to avoid information leakage with DataSAIL","url":"https://www.nature.com/nature-index/article/10.1038/s41467-025-58606-8"},{"title":"Loading Events","url":"https://www.ibs.re.kr/bimag/?p=11067"},{"title":"www.ibs.re.kr","url":"https://www.ibs.re.kr/bimag/events/category/seminar/journal-club/day/2025-06-27/?ical=1"},{"title":"datasail sets sail and new standards for ai testing","url":"https://www.helmholtz-hips.de/en/news-events/news/detail/news/datasail-sets-sail-and-new-standards-for-ai-testing/"},{"title":"Addendum: Data splitting against information leakage with DataSAIL","url":"https://cris.fau.de/publications/359652912"}]

The paper is Joeres, Blument
… [1,645 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: ""AlphaFold2" predicted structures resemble holo apo conformational state pocket side chains study"

Links: [{"title":"AlphaFold2-Based Characterization of Apo and Holo Protein Structures and Conformational Ensembles Using Randomized Alanine Sequence Scanning Adaptation: Capturing Shared Signature Dynamics and Ligand-Induced Conformational Changes","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11641424/"},{"title":"Assessing Structures and Conformational Ensembles of Apo and Holo Protein States Using Randomized Alanine Sequence Scanning Combined with Shallow Subsampling in AlphaFold2 : Insights and Lessons from Predictions of Functional Allosteric Conformations","url":"https://www.biorxiv.org/content/10.1101/2024.11.04.621947.full.pdf"},{"title":"Empowering AlphaFold2 for protein conformation selective drug discovery with AlphaFold2-RAVE","url":"https://arxiv.org/pdf/2404.07102"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC11580948"},{"title":"Published November 3, 2024 | Version v1","url":"https://zenodo.org/record/14031451"},{"title":"Published November 3, 2024 | Version v1","url":"https://zenodo.org/records/14031452"},{"title":"Document Type","url":"https://digitalcommons.chapman.edu/scs_articles/1076"},{"title":"par.nsf.gov","url":"https://par.nsf.gov/servlets/purl/10620819"},{"title":"Empowering AlphaFold2 for protein conformation selective drug discovery with AlphaFold2-RAVE","url":"https://arxiv.or
… [2,694 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:25

```
{"query": "biorxiv ligandable pockets protein-protein interfaces AlphaFold predicted human complexes interactome pocket detection 2024 2025", "mode": "extended"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:26

```
{"query": "\"Leak Proof PDBBind\" LP-PDBBind Li 2023 sequence ligand similarity splits core set results", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "biorxiv ligandable pockets protein-protein interfaces AlphaFold predicted human complexes interactome pocket detection 2024 2025"

Links: [{"title":"A Medicinal Chemistry-Centered Evaluation of AlphaFold 3 and Boltz-2 Across Diverse Binding Modalities","url":"https://www.biorxiv.org/content/10.64898/2026.08.24.746785v1.full"},{"title":"Challenges in predicting PROTAC-mediated Protein-Protein Interfaces with AlphaFold","url":"https://www.biorxiv.org/content/10.1101/2024.03.19.585735v2"},{"title":"ODesign: A World Model for Biomolecular Interaction Design","url":"https://arxiv.org/pdf/2510.22304"},{"title":"Foldseek-Interface reveals a protein interface universe far from complete","url":"https://www.biorxiv.org/content/10.64898/2026.08.24.746585v1.full.pdf"},{"title":"APACE: AlphaFold2 and advanced computing as a service for accelerated discovery in biophysics","url":"https://arxiv.org/pdf/2308.07954"},{"title":"Evolutionary and geometric signatures reveal ligand-binding sites across proteomes","url":"https://www.biorxiv.org/content/10.1101/2025.10.07.680847v1.full"},{"title":"AlphaFold two years on: validation and impact","url":"https://arxiv.org/pdf/2403.02124"},{"title":"Challenges in predicting PROTAC-mediated Protein-Protein Interfaces with AlphaFold reveal a General Limitation on Small Interfaces","url":"https://www.biorxiv.org/content/10.1101/2024.03.19.585735.full.pdf"},{"title":"AlphaBridge: tools for the analysis of predicted biomolecula
… [2,147 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: ""Leak Proof PDBBind" LP-PDBBind Li 2023 sequence ligand similarity splits core set results"

Links: [{"title":"Leak Proof PDBBind: A Reorganized Dataset of Protein-Ligand Complexes for More Generalizable Binding Affinity Prediction","url":"https://arxiv.org/pdf/2308.09639"},{"title":"Leak Proof PDBBind: A Reorganized Dataset of Protein-Ligand Complexes for More Generalizable Binding Affinity Prediction","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10462179/"},{"title":"Leak Proof PDBBind: A Reorganized Dataset of Protein-Ligand Complexes for More Generalizable Binding Affinity Prediction","url":"https://arxiv.org/html/2308.09639v3"},{"title":"Leak Proof PDBBind: A Reorganized Dataset of Protein-Ligand Complexes for More Generalizable Binding Affinity Prediction","url":"https://arxiv.org/html/2308.09639v2"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/2308.09639v3"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2308.09639v2"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10462179.2"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10462179.1"},{"title":"Other Initiatives","url":"https://datasail.readthedocs.io/en/dev/other.html"},{"title":"Leak Proof PDBBind: A Reorganized Dataset of Protein-Ligand Complexes for More Generalizable Binding Affinity Prediction","url":"https://ar5iv.labs.arxiv.org/html/2308.09639"}]

The search returned the original paper and related s
… [2,084 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:34:40

```
{"url": "https://www.biorxiv.org/content/10.1101/600304v2.full", "prompt": "Is this DeeplyTough? Summarize: training data and how training/test splits control for sequence identity or structural similarity; evaluation datasets (TOUGH-M1, Vertex, ProSPECCTs) and AUC numbers for each; runtime/speed claims; any discussion of generalization gaps or data leakage."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:41

```
{"query": "comparison physicochemical properties pockets protein-protein interface inhibitors versus enzyme binding sites hydrophobic flat larger volume analysis", "mode": "standard"}
```


**← tool result**

```
The server returned HTTP 403 Forbidden.

The response body was not retrieved. If this URL requires authentication, use an authenticated tool (e.g. `gh` for GitHub, or an MCP-provided fetch tool) instead of WebFetch.
```


**← tool result**

```
Web search results for query: "comparison physicochemical properties pockets protein-protein interface inhibitors versus enzyme binding sites hydrophobic flat larger volume analysis"

Links: [{"title":"research.pasteur.fr","url":"https://research.pasteur.fr/en/b/KbF"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3901718"},{"title":"Lien vers Pubmed [PMID] – 25285479","url":"https://research.pasteur.fr/fr/b/KbF"},{"title":"Which three-dimensional characteristics make efficient inhibitors of protein-protein interactions?","url":"https://pesquisa.bvsalud.org/ses/resource/es/mdl-25285479"},{"title":"link.springer.com","url":"https://link.springer.com/article/10.1186/2050-6511-14-31"},{"title":"link.springer.com","url":"https://link.springer.com/10.1038/srep18543"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC9294409"},{"title":"academic.oup.com","url":"https://academic.oup.com/bib/article/23/4/bbac165/6598884"},{"title":"schreiber jmb 2004 promate","url":"https://projects.h-its.org/dbase/js/2004-04-26/schreiber-jmb-2004-promate.pdf"},{"title":"minerva-access.unimelb.edu.au","url":"https://minerva-access.unimelb.edu.au/server/api/core/bitstreams/9fd68ab7-0e0c-4534-b29d-9dcede06df8b/content"}]

The search turned up consistent evidence that PPI interfaces differ from enzyme sites, along with some pushback on the older "flat and featureless" picture.

- **Conventional view:** A 2014 J Chem Inf Model study describes
… [1,487 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:34:52

```
{"url": "https://arxiv.org/abs/2003.00193", "prompt": "What paper is this? If it is DeeplyTough by Simonovsky and Meyers, give the abstract and any details on training data, splits, evaluation datasets and AUC values."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:53

```
{"query": "PInet point cloud protein interface prediction Dai Bailey-Kellogg; MaSIF-search surface fingerprint interaction prediction", "mode": "standard"}
```


**← tool result**

```
This page is for **AMAGOLD: Amortized Metropolis Adjustment for Efficient Stochastic Gradient MCMC** (arXiv:2003.00193) by Ruqi Zhang, A. Feder Cooper, and Christopher De Sa. It was submitted in February 2020 and published at AISTATS 2020. It is not the DeeplyTough paper, so the page has no DeeplyTough abstract, training data, splits, evaluation datasets, or AUC values.

The AMAGOLD abstract describes a second-order stochastic gradient MCMC algorithm that "infrequently uses Metropolis-Hastings (M-H) corrections to remove bias." The authors prove convergence with a fixed step size and report experiments on synthetic distributions, Bayesian logistic regression, and Bayesian neural networks.
```


**← tool result**

```
Web search results for query: "PInet point cloud protein interface prediction Dai Bailey-Kellogg; MaSIF-search surface fingerprint interaction prediction"

Links: [{"title":"Structure-based drug design with geometric deep learning","url":"https://arxiv.org/pdf/2210.11250"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC8428585"},{"title":"s41586 023 05993 x","url":"https://www.nature.com/articles/s41586-023-05993-x"},{"title":"MaSIF paper SS2025","url":"https://www-cbi.cs.uni-saarland.de/wp-content/uploads/2025/03/MaSIF-paper_SS2025.pdf"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10131520"},{"title":"Machine learning approaches for the study of protein surfaces","url":"https://www.epfl.ch/labs/lpdi/?p=227"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/606202.full.pdf"},{"title":"Repository logo","url":"https://infoscience.epfl.ch/record/309656"},{"title":"Engineering novel protein interactions with therapeutic potential using deep learning-guided surface design","url":"https://infoscience.epfl.ch/record/310635?ln=en"},{"title":"infoscience.epfl.ch","url":"https://infoscience.epfl.ch/record/273279?ln=en"}]

Here's a summary of what the search returned on both tools.

**PInet (Dai and Bailey-Kellogg, 2021).** The paper appeared in *Bioinformatics* (37(17):2580–2588). PInet is a geometric deep neural network that takes two partner proteins as point clouds and predicts the regions 
… [1,814 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:35:04

```
{"query": "\"DeeplyTough\" Simonovsky Meyers Journal of Chemical Information and Modeling 2020 pocket descriptor AUC Vertex ProSPECCTs", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:35:05

```
{"query": "Fukunishi \"protein-compound affinity matrix\" multiple target screening docking score profile protein similarity Japan", "mode": "standard"}
```


**← tool result**

```
Web search results for query: ""DeeplyTough" Simonovsky Meyers Journal of Chemical Information and Modeling 2020 pocket descriptor AUC Vertex ProSPECCTs"

Links: [{"title":"Your Partner in EMS","url":"https://www.boundtree.com/equipment-bags/bag-accessories/x-deep-stuff-pocket-black/p/2521-16202"},{"title":"deep stuff clear vu pocket","url":"https://rescue-essentials.com/products/deep-stuff-clear-vu-pocket"},{"title":"Property | Similarity |","url":"https://dice.mpi-inf.mpg.de/property/describe-seven-pockets"},{"title":"- data_bias_nsample:","url":"https://deepmd.readthedocs.io/en/v3.0.0a0/genindex.html"},{"title":"victorinox classic sd deep dive limited edtion 2020 0 6223 l2006 swiss pocket knife","url":"https://www.knivesandtools.com/en/pt/-victorinox-classic-sd-deep-dive-limited-edtion-2020-0-6223-l2006-swiss-pocket-knife.htm"},{"title":"#1 Home Improvement Retailer","url":"https://www.homedepot.com/p/questions/TOUGHBUILT-6-25-in-15-Compartment-Large-Technician-10-Pocket-Pouch-Black-TB-CT-36-L10/205918932/1"},{"title":"www.ahlsell.se","url":"https://www.ahlsell.se/en/products/personal-protection/clothes/other-accessories/tool-belts--material-pockets/304313"},{"title":"Bag, Meret X Deep Stuff Pocket","url":"https://www.penncare.net/product/bag-meret-x-deep-stuff-pocket/"},{"title":"Your shopping region is","url":"https://www.goat.com/en-gb/apparel/raf-simons-pocket-distrubed-striped-sweater-red-blue-0459-1fw170105pdss-red"},{"title":"www.ahlsell.se","url":"https://www.ahlse
… [1,597 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "Fukunishi "protein-compound affinity matrix" multiple target screening docking score profile protein similarity Japan"

Links: [{"title":"DOCKSTRING: easy molecular docking yields better benchmarks for ligand design","url":"https://arxiv.org/pdf/2110.15486"},{"title":"Prediction of Protein−compound Binding Energies from Known Activity Data: Docking‐score‐based Method and its Applications","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6055825/"},{"title":"COMET:Combined Matrix for Elucidating Targets","url":"https://arxiv.org/pdf/2412.02471"},{"title":"Quantitative Structure‐activity Relationship (QSAR) Models for Docking Score Correction","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5297997/"},{"title":"10.1007%2FS10822 006 9047 1","url":"https://unpaywall.org/10.1007%2FS10822-006-9047-1"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC5297997"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC6055825"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3521474"},{"title":"researchmap.jp","url":"https://researchmap.jp/ysnbyamashita/published_papers/26407971"},{"title":"dblp.org","url":"https://dblp.org/pid/69/1016"}]

The search turned up a body of work by Yoshifumi Fukunishi and collaborators, mainly on docking-based "protein-compound affinity matrices." It did not turn up a single paper matching your exact description, so I can't confirm w
… [1,783 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:35:18

```
{"url": "https://www.semanticscholar.org/search?q=DeeplyTough%20Learning%20Structural%20Comparison%20of%20Protein%20Binding%20Sites", "prompt": "Find the DeeplyTough paper by Simonovsky and Meyers and report its abstract, venue, year and DOI."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:35:19

```
{"query": "molecular glue induced interface pocket cryptic composite binding site small molecule ternary complex structural analysis review", "mode": "standard"}
```


**← tool result**

```
The server returned HTTP 403 Forbidden.

The response body was not retrieved. If this URL requires authentication, use an authenticated tool (e.g. `gh` for GitHub, or an MCP-provided fetch tool) instead of WebFetch.
```


**← tool result**

```
Web search results for query: "molecular glue induced interface pocket cryptic composite binding site small molecule ternary complex structural analysis review"

Links: [{"title":"GlueFinder: A Data-Driven Framework for the Rational Discovery of Molecular Glues","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12633023/"},{"title":"pubs.rsc.org","url":"https://pubs.rsc.org/en/content/articlehtml/2023/cb/d2cb00207h"},{"title":"Issue 3, 2023","url":"https://pubs.rsc.org/en/Content/ArticleLanding/2023/CB/D2CB00207H"},{"title":"Issue 3, 2023","url":"https://pubs.rsc.org/bn/content/articlelanding/2023/cb/d2cb00207h"},{"title":"cordis.europa.eu","url":"https://cordis.europa.eu/project/id/101098234/reporting"},{"title":"> ## Documentation Index","url":"https://docs.boltz.bio/user-guide/sandbox/Constraints/Example-Contact-with-Molecular-Glues.md"},{"title":"DOI: 10.1021/acs.biochem.6c00427 ISSN: 0006-2960","url":"https://www.citedrive.com/en/discovery/a-molecular-mechanistic-deep-dive-into-1433-molecular-glue-cooperativity/"},{"title":"< back to information centre home","url":"https://www.chemicalprobes.org/info/molecular-glues"},{"title":"< back to information centre home","url":"https://prod1.chemicalprobes.org/info/molecular-glues"},{"title":"< back to information centre home","url":"https://prod2.chemicalprobes.org/info/molecular-glues"}]

The search turned up several relevant sources, mostly from 2023 to 2026.

- **Core review:** Rui, Ashton, Min, Wang and Potts (RSC Chem. Bi
… [2,172 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:35:30

```
{"query": "DeeplyTough protein binding site comparison neural network BenevolentAI 2020 JCIM abstract", "mode": "standard"}
```


**→ tool call `WebFetch`** · 2026-10-27 17:35:32

```
{"url": "https://github.com/BenevolentAI/DeeplyTough", "prompt": "Report the citation (authors, title, journal, year, DOI) and any description of the datasets used (TOUGH-M1, Vertex, ProSPECCTs), training protocol, sequence-identity-based splitting, and reported performance numbers."}
```


**← tool result**

```
Web search results for query: "DeeplyTough protein binding site comparison neural network BenevolentAI 2020 JCIM abstract"

Links: [{"title":"DeeplyTough: Learning Structural Comparison of Protein Binding Sites","url":"https://www.biorxiv.org/content/10.1101/600304.full.pdf"},{"title":"Classification of Protein-Binding Sites Using a Spherical Convolutional Neural Network","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9709917/"},{"title":"PocketMatch: A new algorithm to compare binding sites in protein structures","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2639437/"},{"title":"DeeplyTough: Learning Structural Comparison of Protein Binding Sites","url":"https://cs.paperswithcode.com/paper/deeplytough-learning-structural-comparison-of"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/node/500851"},{"title":"ci9b00554_si_001.pdf (298.17 kB)","url":"https://acs.figshare.com/articles/DeeplyTough_Learning_Structural_Comparison_of_Protein_Binding_Sites/11996316"},{"title":"endnote 8 xml","url":"https://www.biorxiv.org/highwire/citation/500851/endnote-8-xml"},{"title":"UCL Discovery Stage","url":"https://discovery-pp.ucl.ac.uk/id/eprint/10159317"},{"title":"PocketMatch: a new algorithm to compare binding sites in protein structures","url":"https://repository.ias.ac.in/112789"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2639437"}]

The search turned up the DeeplyTough paper by Simonovsky and Meyers (BenevolentAI), but not th
… [1,529 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
**Citation**
- **Title:** DeeplyTough: Learning Structural Comparison of Protein Binding Sites
- **DOI:** 10.1021/acs.jcim.9b00554. The DOI prefix suggests *Journal of Chemical Information and Modeling*, but the page doesn't name the journal.
- **Authors and year:** Not listed. The page's copyright notice reads 2019.

**Datasets**
- The tool supports three benchmarks: TOUGH-M1 (Govindaraj and Brylinski, 2018), Vertex (Chen et al., 2016), and ProSPECCTs (Ehrt et al., 2018).
- These must be downloaded to retrain the network or run these benchmarks. The full set is about 27 GB.
- Downloading ProSPECCTs means accepting its terms of use.
- Raw data can instead be preprocessed with `--db_preprocessing 1`. TOUGH-M1 requires fpocket2 for this.

**Training protocol**
- Needs a GPU with at least 11 GB of memory and takes about 1.5 days on recent hardware. A 4-core CPU is recommended.
- Separate runs are used for each benchmark, with options such as `--seed 4` and dataset-exclusion flags. Vertex and ProSPECCTs runs use `--db_split_strategy 'none'`.
- The page notes that training is non-deterministic, so the pre-trained networks can't be reproduced exactly.

**Sequence-identity splitting**
- The 23.02.2020 changelog entry says the code moved from a UniProt-based split to sequence-based clustering, where "protein structures sharing more than 30% sequence identity" are always placed in the same training or test set.
- The legacy behavior is still available via `--db_split_strategy uniprot_
… [288 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:35:48

```
{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6224041/", "prompt": "List the ProSPECCTs datasets D1 through D7 (including D1.2, D5.2, D6.2 etc.) with a one-line description of what each tests and the number of pairs, especially which ones use NMR structures or test robustness to conformational/structural variation."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:35:50

```
{"query": "Govindaraj Brylinski 2018 \"comparative assessment of strategies to align and compare\" pocket matching TOUGH-M1 BMC Bioinformatics global alignment baseline", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "Govindaraj Brylinski 2018 "comparative assessment of strategies to align and compare" pocket matching TOUGH-M1 BMC Bioinformatics global alignment baseline"

Links: [{"title":"Parameter estimation in Comparative Judgement","url":"https://arxiv.org/pdf/2405.12694"},{"title":"See and Search all TOUGH References »","url":"https://tough.lbl.gov/documentation/tough-research-papers/"},{"title":"See and Search all TOUGH References »","url":"https://tough.lbl.gov/?p=58"},{"title":"escholarship.org","url":"https://escholarship.org/uc/item/0z81w686"},{"title":"[image: image1]On the Bias and Stability of the Results of Comparative Judgment","url":"https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2021.788202/epub"},{"title":"escholarship.org","url":"https://escholarship.org/content/qt4rc7b17t/qt4rc7b17t.pdf"},{"title":"bayesian active learning for multi criteria comparative judgement","url":"https://research-information.bris.ac.uk/en/publications/bayesian-active-learning-for-multi-criteria-comparative-judgement/"},{"title":"American Nuclear Society","url":"https://wx1.ans.org/pubs/journals/nt/a_11749"},{"title":"tough lbl gov","url":"https://git.lsit.ucsb.edu/publicdata/end-of-term-2024/raw/branch/main/seed-lists/sitemap-url-seeds/tough_lbl_gov.txt"},{"title":"a bayesian active learning approach to comparative judgement with","url":"https://research-information.bris.ac.uk/en/publications/a-bayesian-active-learning-approach-to-comparativ
… [732 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
| Dataset | What it tests | Pairs (similar / dissimilar) |
|---|---|---|
| **D1** | Sensitivity to how the binding site is defined, using identical-sequence structures bound to different ligands (12 groups) | 13,430 / 92,846 |
| **D1.2** | Effect of ligand diversity, using identical-sequence structures with similar ligands | 241 / 1,784 |
| **D2** | Sensitivity to binding site flexibility, using models from solution NMR ensembles (17 ensembles of diverse proteins) | 7,729 / 100,512 |
| **D3** | Distinguishing sites that differ in physicochemical properties, using decoys with residue substitutions | 13,430 / 67,150 (full); 13,430 / 13,430 (five-variant subset) |
| **D4** | Distinguishing sites that differ in physicochemical and shape properties, using decoys with residue substitutions | 13,430 / 67,150 (full); 13,430 / 13,430 (five-variant subset) |
| **D5** | Classifying proteins that bind identical ligands or cofactors (Kahraman set, phosphate sites excluded) | 920 / 5,480 |
| **D5.2** | Same as D5 but using the original Kahraman set, with phosphate sites included | 1,320 / 8,680 |
| **D6** | Finding distant relationships between unrelated proteins with identical ligands (Barelier set) | 19 / 43 |
| **D6.2** | Same as D6 but including cofactors (pair counts not listed separately in Table 2) | Not listed separately |
| **D7** | Recovering known binding site similarities among diverse proteins (49 query structures) | 115 / 56,284 |

**NMR and structural-variation datasets:**
-
… [748 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:36:02

```
{"query": "TOUGH-M1 dataset Govindaraj Brylinski comparative assessment pocket matching algorithms BMC Bioinformatics 2018", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:36:03

```
{"query": "\"Simpatico\" protein pocket ligand embedding model binding site", "mode": "standard"}
```


**← tool result**

```
Web search results for query: ""Simpatico" protein pocket ligand embedding model binding site"

Links: [{"title":"Simpatico: accurate and ultra-fast virtual drug screening with atomic embeddings","url":"https://www.biorxiv.org/content/10.1101/2025.06.08.658499.full.pdf"},{"title":"Site2Vec: a reference frame invariant algorithm for vector embedding of protein-ligand binding sites","url":"https://arxiv.org/pdf/2003.08149"},{"title":"A new protein binding pocket similarity measure based on comparison of clouds of atoms in 3D: application to ligand prediction","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2838872/"},{"title":"A Comprehensive Survey of Small-Molecule Binding Pockets in Proteins","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3812058/"},{"title":"DeltaDock: A Unified Framework for Accurate, Efficient, and Physically Reliable Molecular Docking","url":"https://arxiv.org/pdf/2410.11224"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3009464/figure/F2"},{"title":"MSPocket: an orientation-independent algorithm for the detection of ligand binding pockets","url":"https://fis.tu-dresden.de/portal/en/publications/mspocket(4fcd10d1-5e2f-4453-b549-a796460bfa60).html"},{"title":"MSPocket: an orientation-independent algorithm for the detection of ligand binding pockets","url":"https://fis.tu-dresden.de/portal/de/publications/mspocket(4fcd10d1-5e2f-4453-b549-a796460bfa60).html"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/0907.
… [1,792 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "TOUGH-M1 dataset Govindaraj Brylinski comparative assessment pocket matching algorithms BMC Bioinformatics 2018"

Links: [{"title":"ProFSA: Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://arxiv.org/pdf/2310.07229"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/tables/1"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/9"},{"title":"Main content","url":"https://osf.io/6ngbs/wiki/home"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/8"},{"title":"s12859 018 2109 2","url":"https://bmcbioinformatics.biomedcentral.com/track/pdf/10.1186/s12859-018-2109-2"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/11"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/2"},{"title":"Document Type","url":"https://repository.lsu.edu/biosci_pubs/623"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/268565v1"}]

The search confirmed the paper and its dataset, though not the full text of the paper.

- **Paper:** Govindaraj and Brylinski, "Comparat
… [1,370 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:36:19

```
{"url": "https://arxiv.org/html/2310.07229v2", "prompt": "Report ProFSA's benchmark results tables: pocket matching (TOUGH-M1, ProSPECCTs/Vertex) AUC values for ProFSA and baselines including DeeplyTough; pocket druggability prediction results; binding affinity results; and any discussion of data leakage or train/test similarity control."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:36:20

```
{"query": "\"interface pockets\" OR \"interfacial pockets\" druggability analysis predicted protein complexes AlphaFold multimer fpocket large scale study", "mode": "extended"}
```


**← tool result**

```
Web search results for query: ""interface pockets" OR "interfacial pockets" druggability analysis predicted protein complexes AlphaFold multimer fpocket large scale study"

Links: [{"title":"Proteome-Wide Identification and Comparison of Drug Pockets for Discovering New Drug Indications and Side Effects - PMC","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC11767986/"},{"title":"Reliable protein-protein docking with AlphaFold, Rosetta, and replica-exchange","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10402144/"},{"title":"Protein complex prediction with AlphaFold-Multimer","url":"https://www.biorxiv.org/content/10.1101/2021.10.04.463034.full.pdf"},{"title":"Challenges in predicting PROTAC-mediated Protein-Protein Interfaces with AlphaFold reveal a General Limitation on Small Interfaces","url":"https://www.biorxiv.org/content/10.1101/2024.03.19.585735.full.pdf"},{"title":"2022-03-10 Protein complex prediction with AlphaFold-Multimer","url":"https://www.biorxiv.org/content/10.1101/2021.10.04.463034v2.full.pdf"},{"title":"Reliable protein–protein docking with AlphaFold, Rosetta, and replica exchange","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12113263/"},{"title":"Comprehensive detection and characterization of human druggable pockets through binding site descriptors","url":"https://www.nature.com/articles/s41467-024-52146-3"},{"title":"Topological Links in Predicted Protein Complex Structures Reveal Limitations of AlphaFold","url":"https://www.biorxiv.org/conte
… [2,033 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
**Pocket matching (AUC)**

| Setting | Method | Kahraman (w/o PO4) | TOUGH-M1 |
|---|---|---|---|
| Traditional | TM-align | 0.66 | 0.65 |
| Traditional | SiteEngine | 0.64 | 0.73 |
| Traditional | PocketMatch | 0.66 | 0.64 |
| Traditional | IsoMIF | 0.75 | - |
| Zero-shot | Uni-Mol | 0.66 | 0.76 |
| Zero-shot | **ProFSA** | **0.80** | **0.82** |
| Finetuning | DeeplyTough | 0.67 | 0.91 |
| Finetuning | CoSP | 0.62 | - |
| Finetuning | Uni-Mol | 0.71 | 0.79 |
| Finetuning | **ProFSA** | **0.85** | **0.94** |

The page does not mention a "ProSPECCTs/Vertex" results table. It cites Ehrt et al. (2018), the PROSPECCTs benchmark, only as the source of the reduced Kahraman dataset.

**Pocket druggability (RMSE, lower is better)**

| Setting | Method | Fpocket | Druggability | Total SASA | Hydrophobicity |
|---|---|---|---|---|---|
| Finetuning | Uni-Mol | 0.1140 | 0.1001 | 20.73 | 1.285 |
| Finetuning | **ProFSA** | **0.1077** | **0.0934** | **20.01** | **1.275** |
| Zero-shot | Uni-Mol | 0.1419 | 0.1246 | 49.00 | 17.03 |
| Zero-shot | **ProFSA** | **0.1228** | **0.1106** | **30.50** | **13.07** |

**Ligand binding affinity (PDBBind v2019, RMSE / Pearson / Spearman)**

- At 30% sequence identity, ProFSA scores 1.377 / 0.628 / 0.620. The strongest baseline shown is EGNN-PLM at 1.403 / 0.565 / 0.544, and Uni-Mol scores 1.520 / 0.558 / 0.540.
- At 60% sequence identity, Table 3 lists ProFSA at 1.334 / 0.764 / 0.762, ahead of ProNet (1.343 / 0.765 / 0.761) on RMSE and Spearman. ProNet 
… [1,041 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:36:36

```
{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11767986/", "prompt": "Summarize: title, authors, journal, year, DOI; how many pockets identified proteome-wide and from what structures (AlphaFold?); which pocket detection and pocket comparison methods used; main results on drug repurposing/off-target prediction; any runtime/scale statements."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:36:37

```
{"query": "Jubb Blundell Ascher 2015 \"flexibility and small pockets at protein-protein interfaces\" druggability Progress Biophysics findings", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "Jubb Blundell Ascher 2015 "flexibility and small pockets at protein-protein interfaces" druggability Progress Biophysics findings"

Links: [{"title":"Flexibility and small pockets at protein–protein interfaces: New insights into druggability","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4726663/"},{"title":"Structural landscapes of PPI interfaces","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9294409/"},{"title":"Journal article","url":"https://findanexpert.unimelb.edu.au/scholarlywork/1110999-flexibility-and-small-pockets-at-protein-protein-interfaces--new-insights-into-druggability"},{"title":"1 s2.0 S0079610715000103 main","url":"https://biosig.lab.uq.edu.au/media/uploads/publications/1-s2.0-S0079610715000103-main.pdf"},{"title":"www.repository.cam.ac.uk","url":"https://www.repository.cam.ac.uk/handle/1810/247729"},{"title":"Journal article","url":"https://findanexpert.unimelb.edu.au/scholarlywork/1110989-protein-protein-interactions--structures-and-druggability"},{"title":"minerva-access.unimelb.edu.au","url":"https://minerva-access.unimelb.edu.au/server/api/core/bitstreams/9fd68ab7-0e0c-4534-b29d-9dcede06df8b/content"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3158149"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC9294409"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC4117425"}]

The 2015 review by Jubb, Blundell, and Asc
… [1,531 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
**Citation**
- **Title:** Proteome-Wide Identification and Comparison of Drug Pockets for Discovering New Drug Indications and Side Effects
- **Authors:** Renxin Zhang, Zhiyuan Chen, Shuhan Li, Haohao Lv, Jinjun Li, Naixue Yang, Shaoxing Dai
- **Journal:** *Molecules*, 2025 Jan 10;30(2):260
- **DOI:** 10.3390/molecules30020260

**Structures and pocket counts**
- The authors used AlphaFold2-predicted structures for 20,255 human proteins, taken from UniProt's manually reviewed entries.
- Fpocket identified 15,043 druggable pockets (drug score above 0.5), spanning 11,378 druggable proteins. A drug score above 0.5 defines a pocket as druggable.
- P2Rank found 7,985 pockets in 6,113 proteins, and PUResNetV2 found 14,450 pockets in 11,378 proteins. 4,069 proteins were flagged by all three tools.

**Methods**
- **Pocket detection:** Fpocket was the primary tool, with P2Rank and PUResNetV2 run in parallel for comparison.
- **Pocket comparison:** Apoc, with pairs counted as similar at p < 0.0001.
- **Scale:** About 76.25 million intra-proteome pocket pairs were compared, yielding 220,312 similar pairs, 3,241 of which spanned different families. Against 1,872 known drug pockets, about 23.1 million pairs were compared, yielding 62,077 similar pairs.

**Main results**
- **Drug repositioning (docking-validated with AutoDock Vina):**
  - Progesterone to ADGRD1 (−6.9 kcal/mol), linked to pemphigus and breast cancer.
  - Estradiol to ANO2 (−7.3 kcal/mol), linked to shingles and medulloblasto
… [1,190 more characters; full text in agent_logs/raw/]
```


### Assistant · 2026-10-27 17:37:59

I have gathered the material. Writing up the report now.


**→ tool call `SubagentHandback`** · 2026-10-27 17:40:57

```
{"message": "# Literature review: docking-profile pocket descriptors, PPI-interface pockets, and leakage/robustness\n\nEverything below is sourced; items I could **not** verify from a primary source are explicitly flagged `[UNVERIFIED]`. Numbers extracted from full texts are quoted as the paper gives them.\n\n---\n\n## 1. Docking-profile / ligand-based pocket descriptors\n\n### 1.1 PocketVec — the reference implementation of the idea\n\n**Citation.** Comajuncosa-Creus, Jorba, Barril, Aloy, \"Comprehensive detection and characterization of human druggable pockets through binding site descriptors\", *Nat Commun* **15** (2024), DOI `10.1038/s41467-024-52146-3`; preprint bioRxiv `10.1101/2024.03.14.584971`. (Note: there is **no author named Balboa** — that attribution in the brief is wrong.)\n\n**Ligand set.** The production pipeline docks **128 lead-like molecules (LLM)**. Provenance: 650k lead-like molecules → k-means clustering on TAT fingerprints → 1,000 representative LLM (MOE v2019.01, MW 200–450 Da) → the **128 most diverse by Shannon entropy**. A **667-compound Glide fragment set (MW 50–200)** was explicitly tested and **performed worse**. The paper's reasoning: \"LLM occupied a larger fraction of the binding sites than fragments\" and \"LLM showed a superior discriminative power with respect to the size of the pocket.\" Outlier (positive) docking scores \"were rare with fragments but more frequent when using LLM.\"\n\n**Docking engine.** **rDock, rigid** docking, default
… [32,675 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```
