# Sub-agent ae2f32721ac9ffb42 — Pocket comparison methods catalog (?)

Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to 1,500 characters; assistant text is complete. Thinking blocks are included where stored as text.


### PI / user turn · 2026-10-27 17:30:09

You are helping write a literature review for a project building a FAST protein binding-pocket SIMILARITY method (sequence/fold independent) for AlphaFold-DB scale (~200M structures). Your job: a METHODS CATALOG. Return a dense factual text report (do not write files). Load WebSearch/WebFetch via ToolSearch query "select:WebSearch,WebFetch". Network works from bash too (curl, pip index, e.g. `pip download --no-deps -d /tmp/x pkg` is NOT allowed; use `curl -s https://pypi.org/pypi/<pkg>/json | head -c 300` or anaconda.org pages to check installability, and GitHub pages to check code availability/licence/last commit).

For each method report: year + venue + DOI; representation (atoms/pseudocenters/surface points/graph/grid/learned embedding/docking profile); comparison scheme (alignment-based: clique/geometric hashing/ICP/graph matching; alignment-free fingerprint; learned embedding; ligand/docking-profile); reported runtime per comparison (quote numbers + source; mark unknown); code availability (URL, licence, pip/conda installable? binary only? web server only?); one-line strengths/weaknesses; whether it was applied to AlphaFold models or PPI interfaces.
Methods: SiteEngine (and I2I-SiteEngine for interfaces), G-LoSA, APoc, ProBiS (and ProBiS-Dock / ProBiS-Fold, ProBiS H2O), IsoMIF (and IsoMIF Finder), KRIPO, FuzCav, Cavbase, SiteAlign, SiteMine, SiteContext? (verify), Siteomix? (verify existence), POEM subpocket similarity (verify), metal-binding-site ICP alignment (e.g. "MetalSiteHunter"? find the actual paper), Folddisco (Steinegger lab 2025, motif search at AFDB scale), pyScoMotif, ActSeek, ACP4 (verify), KiSSim (kinase), FUSED (verify), SiteMatcher (verify), DeeplyTough (Simonovsky & Meyers 2020 JCIM), spherical-CNN pocket classification (verify), GraphSite, PocketAnchor, ProFSA (Gao et al. 2023/2024 ICLR), LEN-Seek? (verify), GTA-5 (verify - maybe a graph transformer approach?), DMPPS (verify), DrugCLIP (Gao et al. NeurIPS 2023; and the 2025/2026 Science "genome-wide virtual screening" with DrugCLIP / GenomeScreenDB), LigUnity, BindCLIP, Simpatico, EPoCS (verify), PocketScope (verify), ErePOC, OneProt, Foldseek, MMseqs2, ECIFP (verify - extended connectivity interaction features fingerprints?), MaSIF / MaSIF-ligand / MaSIF-search (surface fingerprints, relevant for PPI), PocketMatch, SMAP, TM-align-pocket/PSA, PocketFEATURE, eMatchSite, BSSF/ VolSite/Shaper, PocketShape, TrixP, RAPMAD, PSIM, Shaper, BioGPS, Grim, PocketGraph, SiteRadar, PLIP/interaction-fingerprint-based comparisons (e.g. PLIP-based function annotation, "binding site similarity via interaction fingerprints"), PDBspheres, LabelHash. Many of the names in the list are obscure or possibly misnamed — for each, either find the actual paper or report "could not find / may not exist".

Also look specifically for fast alignment-free ideas: learned embeddings + vector search (FAISS) at scale, shape/pharmacophore histograms (e.g. FuzCav triplets, PocketMatch distance distributions, Ultrafast shape recognition USR applied to pockets), optimal transport / Wasserstein / point-cloud kernels for pockets, Zernike descriptors (3D Zernike for pockets, Kihara lab), persistent homology. Report any published runtimes (comparisons/second) for large-scale all-vs-all.

Be strict: never invent numbers, DOIs, or URLs; mark unverified items. Target ~2500-3500 words plus a reference list with DOIs.


### PI / user turn · 2026-10-27 17:30:09

<system-reminder>
Your final report is delivered through SubagentHandback: when your work is complete, call SubagentHandback({message: <your full report>}). The call ends your run, so make it your last step. Only a SubagentHandback call reaches your caller as your result; plain text you write at the end is not delivered. Do not also send the report with SendMessage: your caller would get it twice.
</system-reminder>


**→ tool call `ToolSearch`** · 2026-10-27 17:30:11

```
{"query": "select:WebSearch,WebFetch", "max_results": 2}
```


**← tool result**

```
[non-text content]
[non-text content]
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:14

```
{"query": "Folddisco motif search AlphaFold database Steinegger 2025", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:14

```
{"query": "ActSeek active site search AlphaFold structures", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:15

```
{"query": "pyScoMotif structural motif search", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:15

```
{"query": "DrugCLIP genome-wide virtual screening Science GenomeScreenDB", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:16

```
{"query": "ProFSA protein fragment-surroundings alignment pocket pretraining ICLR", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "DrugCLIP genome-wide virtual screening Science GenomeScreenDB"

Links: [{"title":"Deep contrastive learning enables genome-wide virtual screening","url":"https://www.biorxiv.org/content/10.1101/2024.09.02.610777.full.pdf"},{"title":"Wei Zhang's group published 'Deep contrastive learning enables genome-wide virtual screening' in Science","url":"https://mcgovern.life.tsinghua.edu.cn/en/infoshow-2898.html"},{"title":"Ultrafast genome-wide virtual screening with DrugCLIP. Credit: Science (2026). DOI: 10.1126/science.ads9530","url":"https://scour.ing/@matmat/p/https://phys.org/news/2026-01-ai-tool-discovery-life-medicines.html"},{"title":"ground breaking drugclip offers ai driven ultra fast drug virtual screening","url":"https://www.insideprecisionmedicine.com/topics/precision-medicine/ground-breaking-drugclip-offers-ai-driven-ultra-fast-drug-virtual-screening"},{"title":"deep contrastive learning enables genome wide virtual screening","url":"https://scholars.cityu.edu.hk/en/publications/deep-contrastive-learning-enables-genome-wide-virtual-screening/"},{"title":"hyper.ai","url":"https://hyper.ai/en/stories/438742dda342cb9938a44d71c1af0766"},{"title":"Chinese Scientists Develop AI-Driven Ultra-Fast Drug Screening Platform","url":"https://www2.yicaiglobal.com/news/chinese-scientists-develop-ai-driven-ultra-fast-drug-screening-platform"},{"title":"9JF3 | pdb_00009jf3","url":"https://www2.rcsb.org/structure/9jf3"},{"title":"c 1155835","url":"https://reg
… [1,742 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "pyScoMotif structural motif search"

Links: [{"title":"pyScoMotif: Discovery of similar 3D structural motifs across proteins","url":"https://www.biorxiv.org/content/10.1101/2023.08.27.554982.full.pdf"},{"title":"pyScoMotif: discovery of similar 3D structural motifs across proteins","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10640396/"},{"title":"pypi.org","url":"https://pypi.org/project/pyscomotif/0.9.20"},{"title":"ulb.ac.be","url":"https://dipot.ulb.ac.be/dspace/bitstream/2013/367924/3/vbad158.pdf"},{"title":"دورية أكاديمية","url":"https://nufind.nu.edu.sa/EdsRecord/edb,179072796"},{"title":"par Cia Beriain, Gabriel","url":"https://difusion.ulb.ac.be/vufind/Record/ULB-DIPOT:oai:dipot.ulb.ac.be:2013/367924/TOC"},{"title":"assets-eu.researchsquare.com","url":"https://assets-eu.researchsquare.com/files/rs-7273586/v1/6c2eb3a1c3276b4af342b81c.pdf"},{"title":"Faculty       Staff       Contact       Institute Directory","url":"https://www.cs.rpi.edu/research/phdabstracts/zhangy.html"},{"title":"14 Structured Motifs Search","url":"https://cse.buet.ac.bd/assets/docs/ThesisPosterFeb2015/14_Structured Motifs Search.pdf"},{"title":"pubannotation.org","url":"https://pubannotation.org/docs/sourcedb/PMC/sourceid/1679804"}]

pyScoMotif is an open-source Python package for finding similar 3D structural motifs across protein structures, published in Bioinformatics Advances in 2023 by Cia, Kwasigroch, Stamatopoulos, Rooman, and Pucci.

- **Method:** It 
… [1,328 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "ActSeek active site search AlphaFold structures"

Links: [{"title":"ActSeek: fast and accurate search algorithm of active sites in alphafold database","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12343037/"},{"title":"ActSeek: Fast and accurate search algorithm of active sites in Alphafold database","url":"https://www.biorxiv.org/content/10.1101/2025.02.11.637678.full.pdf"},{"title":"actseek fast and accurate search algorithm of active sites in alp","url":"https://cris.vtt.fi/en/publications/actseek-fast-and-accurate-search-algorithm-of-active-sites-in-alp/"},{"title":"AlphaFind — discover structure similarity across the proteome in AlphaFold DB","url":"https://ics.muni.cz/en/research/publications/2441940"},{"title":"search structures","url":"https://glama.ai/mcp/servers/Augmented-Nature/AlphaFold-MCP-Server/tools/search_structures"},{"title":"AlphaFind — discover structure similarity across the proteome in AlphaFold DB","url":"https://www.ics.muni.cz/veda-a-vyzkum/publikace/2441940"},{"title":"AlphaFold database empowers researchers with enhanced structural search via Foldseek integration","url":"https://www.ebi.ac.uk/about/news/updates-from-data-resources/alphafold-foldseek/"},{"title":"AlphaFind: discover structure similarity across the proteome in AlphaFold DB","url":"https://www.phil.muni.cz/vyzkum/publikace/prehled/2402219"},{"title":"Tools and Applications","url":"https://cerit-sc.cz/infrastructure-services/tools-and-applications"}
… [1,673 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "Folddisco motif search AlphaFold database Steinegger 2025"

Links: [{"title":"Structural motif search across the protein-universe with Folddisco","url":"https://www.biorxiv.org/content/10.1101/2025.07.06.663357.full.pdf"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/node/5257617"},{"title":"Seoul National University Team Develops \"FoldDisco,\" an Ultra-Fast Protein Structure Search Tool","url":"https://view.asiae.co.kr/en/article/2026061110053638883"},{"title":"Team led by SNU professor Martin Steinegger","url":"https://biz.heraldcorp.com/article/10779615"},{"title":"mbiz.heraldcorp.com","url":"https://mbiz.heraldcorp.com/article/10779615"},{"title":"bioinformaticshome.com","url":"https://bioinformaticshome.com/db/tool/folddisco"},{"title":"mail.cgl.ucsf.edu","url":"https://mail.cgl.ucsf.edu/mailman/archives/list/chimerax-users@cgl.ucsf.edu/message/JEGUJNMQHAIL4MWAGA54TJ2D5NDF2JHG/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/pmid/37156916"},{"title":"AlphaFold Protein Structure Database 2025: a redesigned interface and updated structural coverage","url":"https://tagteam.harvard.edu/hub_feeds/4353/feed_items/17201859/about"},{"title":"github.com","url":"https://github.com/steineggerlab/foldseek/releases"}]

Folddisco is a structural motif search tool from Martin Steinegger's lab at Seoul National University, with first author Hyunbin Kim. Its bioRxiv preprint carries a 2025 DOI (10.1101/2025.07.06.
… [1,434 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "ProFSA protein fragment-surroundings alignment pocket pretraining ICLR"

Links: [{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://proceedings.iclr.cc/paper_files/paper/2024/hash/6cc31b44d88dce8380d36e81485cd07f-Abstract-Conference.html"},{"title":"iclr.cc","url":"https://ICLR.cc/virtual/2024/poster/17577"},{"title":"openreview.net","url":"https://openreview.net/pdf/fcb728a7e3b8f50b0b315d0afbd69ca490308c3e.pdf"},{"title":"License: arXiv.org perpetual non-exclusive license","url":"https://arxiv.org/html/2310.07229v2"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2310.07229v1"},{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://ar5iv.labs.arxiv.org/html/2310.07229"},{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://chatpaper.com/fr/paper/7088"},{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://chatpaper.com/de/paper/7088"},{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://chatpaper.com/es/paper/7088"},{"title":"self supervised pocket pretraining via","url":"https://sotaverified.org/papers/self-supervised-pocket-pretraining-via"}]

ProFSA is a self-supervised pocket pretraining method published at ICLR 2024, titled "Self-supervised Pocket Pretraining via Protein Fragment-Sur
… [1,763 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:25

```
{"query": "Folddisco Nature 2026 Kim Steinegger structural motif published", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:26

```
{"query": "DeeplyTough Simonovsky Meyers 2020 JCIM pocket matching", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:26

```
{"query": "PocketAnchor learning structure-based pocket representations", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:27

```
{"query": "LigUnity foundation model pocket ligand virtual screening hit-to-lead", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:27

```
{"query": "BindCLIP contrastive pocket ligand", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "PocketAnchor learning structure-based pocket representations"

Links: [{"title":"www.researchsquare.com","url":"https://www.researchsquare.com/article/rs-1583468/v1"},{"title":"Generating Developable 3D Molecules via Pocket-Conditioned Diffusion and Property-Aware Optimization","url":"https://arxiv.org/pdf/2607.12349"},{"title":"hub.docker.com","url":"https://hub.docker.com/r/tiantz17/pocketanchor"},{"title":"hub.docker.com","url":"https://hub.docker.com/u/tiantz17"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2310.07229v1"},{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://proceedings.iclr.cc/paper_files/paper/2024/hash/6cc31b44d88dce8380d36e81485cd07f-Abstract-Conference.html"},{"title":"Self-supervised Pocket Pretraining via Protein Fragment-Surroundings Alignment","url":"https://ar5iv.labs.arxiv.org/html/2310.07229"},{"title":"openreview.net","url":"https://openreview.net/pdf/fcb728a7e3b8f50b0b315d0afbd69ca490308c3e.pdf"},{"title":"iclr.cc","url":"https://ICLR.cc/virtual/2024/poster/17577"},{"title":"self supervised pocket pretraining via","url":"https://sotaverified.org/papers/self-supervised-pocket-pretraining-via"}]

The main source is a Research Square preprint that introduces PocketAnchor, a structure-based protein representation method for protein-ligand interaction tasks. It defines "anchors" as probe points that reach into cavities or sit near the protein surface, and uses 
… [1,233 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "BindCLIP contrastive pocket ligand"

Links: [{"title":"Contrastive Multi-Task Learning with Solvent-Aware Augmentation for Drug Discovery","url":"https://arxiv.org/pdf/2508.01799"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/2602.15236"},{"title":"BindCLIP: A Unified Contrastive–Generative Representation Learning Framework for Virtual Screening","url":"https://arxiv.org/html/2602.15236v1"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2602.15236v1"},{"title":"arxiv.org","url":"https://arxiv.org/html/2310.06367v1"},{"title":"License: arXiv.org perpetual non-exclusive license","url":"https://arxiv.org/html/2310.07229v2"},{"title":"openreview.net","url":"https://openreview.net/pdf/fcb728a7e3b8f50b0b315d0afbd69ca490308c3e.pdf"},{"title":"DrugCLIP: Contrastive Protein-Molecule Representation Learning for Virtual Screening","url":"https://papers.neurips.cc/paper_files/paper/2023/hash/8bd31288ad8e9a31d519fdeede7ee47d-Abstract-Conference.html"},{"title":"Next Issue","url":"https://www.mdpi.com/3042-6723/1/2"},{"title":"hyper.ai","url":"https://hyper.ai/news/37912"}]

BindCLIP is a 2026 arXiv paper (arXiv:2602.15236, submitted February 16, 2026) by Anjie Qiao, Zhen Wang, Yaliang Li, Jiahua Rao, and Yuedong Yang. It is a contrastive-generative framework for virtual screening.

- **Core approach:** The model jointly trains pocket and ligand encoders with a CLIP-style contrastive objective plus a pocket-conditioned diffusion objective for binding 
… [1,129 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "DeeplyTough Simonovsky Meyers 2020 JCIM pocket matching"

Links: [{"title":"DeeplyTough: Learning Structural Comparison of Protein Binding Sites","url":"https://www.biorxiv.org/content/10.1101/600304.full.pdf"},{"title":"dblp.uni-trier.de","url":"https://dblp.uni-trier.de/pid/185/0737"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/8"},{"title":"gitlab.rrz.uni-hamburg.de","url":"https://gitlab.rrz.uni-hamburg.de/cosy-bio/drugst.one/frontend/-/blob/9b88b6727d617865d467e1c723caeb7d897a925f/tsconfig.spec.json"},{"title":"Congrats to Yunhui and Si on new JCIM paper","url":"https://sites.temple.edu/voelzlab/2021/04"},{"title":"gitlab.rrz.uni-hamburg.de","url":"https://gitlab.rrz.uni-hamburg.de/baw8330/projekt-cis-biochemie-2021-22/-/commit/004d7d8aaae4c3ce7e21e53a8f7e1c7ece314181?expanded=1"},{"title":"www.h-its.org","url":"https://www.h-its.org/de/wp-json/wp/v2/posts/35288"},{"title":"otree servers.yml.example","url":"https://gitlab.rrz.uni-hamburg.de/wiso-forschungslabor/otree-ansible/-/blob/714349ae569b6f261ce9380775590344c01ee3af/group_vars/otree_servers.yml.example"},{"title":"www.bu.edu","url":"https://www.bu.edu/bmerc/wp-json/wp/v2/posts/334"},{"title":"Recent article among the most read in JCIM","url":"https://www.bu.edu/bmerc/2013/06/01/recent-article-among-the-most-read-in-jcim"}]

The search confirmed the paper and its basic details, though it re
… [1,015 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "LigUnity foundation model pocket ligand virtual screening hit-to-lead"

Links: [{"title":"Hierarchical affinity landscape navigation through learning a shared pocket-ligand space","url":"https://www.biorxiv.org/content/10.1101/2025.02.17.638554.full.pdf"},{"title":"Hierarchical affinity landscape navigation through learning a shared pocket-ligand space","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12546767/"},{"title":"Generative Modeling in Protein Design: Neural Representations, Conditional Generation, and Evaluation Standards","url":"https://arxiv.org/pdf/2603.26378"},{"title":"Mozi: Governed Autonomy for Drug Discovery LLM Agents","url":"https://arxiv.org/pdf/2603.03655"},{"title":"h-MINT: Modeling Pocket-Ligand Binding with Hierarchical Molecular Interaction Network","url":"https://arxiv.org/pdf/2604.23134"},{"title":"LigUnity / README.md","url":"https://huggingface.co/Irwiny/LigUnity/blob/main/README.md"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2025.02.17.638554v2"},{"title":"YAML Metadata Warning:empty or missing yaml metadata in repo card","url":"https://huggingface-gw-kz.just-ai.com/Irwiny/LigUnity"},{"title":"app.alphaneural.io","url":"https://app.alphaneural.io/assets/Irwiny/LigUnity"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/2601.09693v1"}]

LigUnity is a protein-ligand affinity foundation model from Feng et al. (bioRxiv preprint, 2025) that targets both virtual screening and hit-to-l
… [1,930 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "Folddisco Nature 2026 Kim Steinegger structural motif published"

Links: [{"title":"Structural motif search across the protein-universe with Folddisco","url":"https://www.biorxiv.org/content/10.1101/2025.07.06.663357.full.pdf"},{"title":"General Multimodal Protein Design Enables DNA-Encoding of Chemistry","url":"https://arxiv.org/pdf/2604.05181"},{"title":"mbiz.heraldcorp.com","url":"https://mbiz.heraldcorp.com/article/10779615"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/node/5257617"},{"title":"Team led by SNU professor Martin Steinegger","url":"https://biz.heraldcorp.com/article/10779615"},{"title":"Seoul National University Team Develops \"FoldDisco,\" an Ultra-Fast Protein Structure Search Tool","url":"https://view.asiae.co.kr/en/article/2026061110053638883"},{"title":"bioinformaticshome.com","url":"https://bioinformaticshome.com/db/tool/folddisco"},{"title":"“단 몇초면 끝” 5300만개 단백질 구조 분석…서울대, 초고속 검색도구 개발","url":"https://www.heraldk.com/article/2026061019000073956"},{"title":"assets-eu.researchsquare.com","url":"https://assets-eu.researchsquare.com/files/rs-7273586/v1/6c2eb3a1c3276b4af342b81c.pdf"},{"title":"bioengineer.org","url":"https://bioengineer.org/?p=357320"}]

The search confirms the Folddisco paper was published in *Nature Biotechnology* in 2026, with Martin Steinegger as senior author and Hyunbin Kim as a lead author. I found no separate Nature (flagship) listing, so the journal is *Nature Biotechnology*.

- **Publica
… [1,253 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:37

```
{"query": "\"Folddisco\" \"Nature Biotechnology\" doi", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:37

```
{"query": "Simpatico protein ligand binding site similarity contrastive embedding", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:38

```
{"query": "ErePOC pocket embedding ESM representation", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:38

```
{"query": "PocketScope binding pocket", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:30:39

```
{"query": "EPoCS pocket comparison", "mode": "standard"}
```


**← tool result**

```
Web search results for query: ""Folddisco" "Nature Biotechnology" doi"

Links: [{"title":"parts property and sharing","url":"https://portal.fis.tum.de/en/publications/parts-property-and-sharing/"},{"title":"libsearch.um.ac.ir","url":"https://libsearch.um.ac.ir/fum/handle/fum/698777?show=full"},{"title":"peeref.com","url":"https://peeref.com/works/1113873"},{"title":"Original language | English (US) |","url":"https://asu.elsevierpure.com/en/publications/corporate-responsibilities"},{"title":"time to drop the language of consensus","url":"https://experts.umn.edu/en/publications/time-to-drop-the-language-of-consensus/"},{"title":"b5a0d2af 6557 408f 88ac a34a226f617c","url":"https://www.scienceopen.com/document/vid/b5a0d2af-6557-408f-88ac-a34a226f617c"},{"title":"letter to the editor 11","url":"https://pure.psu.edu/en/publications/letter-to-the-editor-11/"},{"title":"Publication Title","url":"https://digitalcommons.providence.org/publications/3092"},{"title":"toward effective software solutions for big biology","url":"https://researchinformation.umcutrecht.nl/en/publications/toward-effective-software-solutions-for-big-biology/"},{"title":"- Preview Available","url":"https://www.proquest.com/docview/204478208"}]

The search didn't find the Folddisco paper. None of the 10 results mention "Folddisco," so I can't give you its DOI from these results.

The results were Nature Biotechnology articles from various years (1996 to 2021) with DOIs, but none matched the Folddisco title or top
… [341 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "ErePOC pocket embedding ESM representation"

Links: [{"title":"Deciphering DEL Pocket Patterns through Contrastive Learning","url":"https://www.biorxiv.org/content/10.1101/2025.06.12.659183.full.pdf"},{"title":"Nature Communications (Feb 2026)","url":"https://doaj.org/article/3043c09aa2b74443b9b87ced7dfeeabb"},{"title":"Mapping the space of protein binding sites with sequence-based protein language models","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12208174/"},{"title":"SpliceBind: Isoform-Aware Prediction of Binding Pocket Druggability","url":"https://arxiv.org/pdf/2606.04020"},{"title":"Molecular Embedding-Based Algorithm Selection in Protein-Ligand Docking","url":"https://arxiv.org/pdf/2512.02328"},{"title":"HonestAffinity: Leak-Aware Evaluation of Protein and Pocket Priors for Binding Affinity Prediction","url":"https://arxiv.org/pdf/2606.03422"},{"title":"Mapping the space of protein binding sites with sequence-based protein language models","url":"https://www.biorxiv.org/content/10.1101/2024.07.24.604735.full.pdf"},{"title":"A general language model for peptide function identification","url":"https://arxiv.org/pdf/2502.15610"},{"title":"Generating Developable 3D Molecules via Pocket-Conditioned Diffusion and Property-Aware Optimization","url":"https://arxiv.org/pdf/2607.12349"},{"title":"PockNet / README.md","url":"https://huggingface.co/lal3lu03/PockNet/blob/main/README.md"}]

The search turned up a few sources on ErePOC and rela
… [1,055 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "EPoCS pocket comparison"

Links: [{"title":"Estimating the Similarity between Protein Pockets","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9604425/"},{"title":"nih.gov","url":"https://pubmed.ncbi.nlm.nih.gov/23335017"},{"title":"A new protein binding pocket similarity measure based on comparison of 3D atom clouds: application to ligand prediction","url":"https://arxiv.org/pdf/0907.1531"},{"title":"Wafer carrier","url":"https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10490432"},{"title":"- ← Back to all Pledge Levels","url":"https://www.backerkit.com/c/projects/dapper-design/epicforged-pocket-edc-organizer/pledge_levels/1724"},{"title":"Garment having an improved pocket construction","url":"https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9968147"},{"title":"- ← Back to all Pledge Levels","url":"https://www.backerkit.com/c/projects/dapper-design/epicforged-pocket-edc-organizer/pledge_levels/1720"},{"title":"GENEOnet: A new machine learning paradigm based on Group Equivariant Non-Expansive Operators. An application to protein pocket detection","url":"https://arxiv.org/pdf/2202.00451"},{"title":"Pocket comparator","url":"https://en.wikipedia.org/wiki/Pocket_comparator"},{"title":"salinger 01a 0312","url":"https://grouper.ieee.org/groups/802/3/epoc/public/mar12/salinger_01a_0312.pdf"},{"title":"bioinformation.net","url":"https://bioinformation.net/015/97320630015295.pdf"},{"title":"psorting 8c source","url":"
… [1,926 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "PocketScope binding pocket"

Links: [{"title":"PocketScout MCP","url":"https://glama.ai/mcp/servers/Proprius-Labs/pocketscout-mcp"},{"title":"Evolutionary and geometric signatures reveal ligand-binding sites across proteomes","url":"https://www.biorxiv.org/content/10.1101/2025.10.07.680847.full.pdf"},{"title":"Method for affinity scoring of peptide/protein complexes","url":"https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8538706"},{"title":"PocketPicker: analysis of ligand binding-sites with shape descriptors","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1994066/"},{"title":"Using Multiple Microenvironments to Find Similar Ligand-Binding Sites: Application to Kinase Inhibitor Binding","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3248393/"},{"title":"Analysis of shape, properties and \"druggability\" of protein binding pockets","url":"https://core.ac.uk/works/6091637"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/1471-2105-10-168/figures/2"},{"title":"Comprehensive detection and characterization of human druggable pockets through novel binding site descriptors","url":"https://www.biorxiv.org/content/10.1101/2024.03.14.584971.full.pdf"},{"title":"www.henryschein.com","url":"https://www.henryschein.com/us-es/medical/p/equipment/diagnostic-tools/pocketscope-set-w-aa/5669534"},{"title":"PickPocket Enables Binding Site Prediction at the Proteome Scale"
… [2,888 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "Simpatico protein ligand binding site similarity contrastive embedding"

Links: [{"title":"Simpatico: accurate and ultra-fast virtual drug screening with atomic embeddings","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12259003/"},{"title":"Simpatico: accurate and ultra-fast virtual drug screening with atomic embeddings","url":"https://www.biorxiv.org/content/10.1101/2025.06.08.658499.full.pdf"},{"title":"Site2Vec: a reference frame invariant algorithm for vector embedding of protein-ligand binding sites","url":"https://arxiv.org/pdf/2003.08149"},{"title":"Site2Vec: a reference frame invariant algorithm for vector embedding of protein-ligand binding sites","url":"https://paperswithcode.com/paper/site2vec-a-reference-frame-invariant"},{"title":"Site2Vec: a reference frame invariant algorithm for vector embedding of protein-ligand binding sites","url":"https://ar5iv.labs.arxiv.org/html/2003.08149"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2003.08149v2"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2003.08149v1"},{"title":"site2vec a reference frame invariant","url":"https://sotaverified.org/papers/site2vec-a-reference-frame-invariant"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/2003.08149v2"},{"title":"License: arXiv.org perpetual non-exclusive license","url":"https://arxiv.org/html/2312.03016v1"}]

Simpatico is a virtual screening tool rather than a binding-site similarity tool, though it does touch on protein similarit
… [1,704 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:30:49

```
{"url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12208174/", "prompt": "Give title, authors, journal, year, DOI, what EPoCS stands for, how pocket representation is built, runtime numbers, code URL, applied to AlphaFold models? benchmark (ProSPECCTs) results."}
```


**→ tool call `WebFetch`** · 2026-10-27 17:30:50

```
{"url": "https://sciety.org/articles/activity/10.64898/2026.08.30.748136", "prompt": "Give title, authors, date, DOI, method name, how it works, runtime numbers, code URL, benchmarks."}
```


**→ tool call `WebFetch`** · 2026-10-27 17:30:51

```
{"url": "https://www.biorxiv.org/content/10.1101/2025.06.12.659183.full.pdf", "prompt": "Give title, authors, DOI, what ErePOC is, representation, comparison metric, runtime, code URL, published venue if mentioned."}
```


**← tool result**

```
REDIRECT DETECTED: The URL redirects to a location that was not fetched automatically.

    Original URL: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12208174/
    Redirect URL (from the server's Location header — server-supplied, not verified): https://pmc.ncbi.nlm.nih.gov/articles/PMC12208174/
    Status: 301 Moved Permanently

    To complete your request, I need to fetch content from the redirected URL. Please use WebFetch again with these parameters:
    - url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC12208174/"
    - prompt: "Give title, authors, journal, year, DOI, what EPoCS stands for, how pocket representation is built, runtime numbers, code URL, applied to AlphaFold models? benchmark (ProSPECCTs) results."
```


**← tool result**

```
**Title:** Retrieval of binding sites across the AlphaFold human proteome using protein language model representations

**Authors:** Keshav Mohan, Yash Bhargava

**Date:** Sep 3, 2026 (version published to bioRxiv)

**DOI:** 10.64898/2026.08.30.748136

**Method:** PocketScope

**How it works:** It is training-free. It represents cavity-lining residues with frozen ESM-C 600M embeddings. It then retrieves related binding sites by comparing residues with exhaustive late-interaction MaxSim, without pooling embeddings or using approximate nearest-neighbor search.

**Runtime numbers:** The provided content gives no runtime or timing figures. It reports only scale: 153,805 cavities identified across 37,682 proteins in the AlphaFold human proteome.

**Code URL:** The page says PocketScope is open source but gives no repository link. The web server is at https://www.bhargavaresearch.org/pocketscope

**Benchmarks:**
- On the ProSPECCTs benchmark, PocketScope ranks 1st of 23 methods by mean rank across ten collections.
- It recovered documented drug off-targets across a curated set of pharmacological pairs. The page gives no numbers for this result.
```


**← tool result**

```
The provided content doesn't include the article's text, so I can only confirm the title:

- **Title:** "Deciphering DEL Pocket Patterns through Contrastive Learning" (from the PDF metadata)
- **Authors:** Not found
- **DOI:** Not found
- **What ErePOC is:** Not found
- **Representation:** Not found
- **Comparison metric:** Not found
- **Runtime:** Not found
- **Code URL:** Not found
- **Published venue:** Not found

The dump is mostly compressed, binary PDF data, and the rest is truncated, so the article's body and front matter aren't readable. If you paste the extracted text of the first page or the abstract, I can pull out the remaining fields.

[Binary content (application/pdf, 3.5MB) also saved to /home/.claude/projects/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/tool-results/webfetch-1793122257463-7vnvar.pdf]
```


**→ tool call `WebFetch`** · 2026-10-27 17:31:03

```
{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12208174/", "prompt": "Give title, authors, journal, year, DOI, what EPoCS stands for, how pocket representation is built, runtime numbers, code URL, applied to AlphaFold models? benchmark (ProSPECCTs) results."}
```


**→ tool call `WebFetch`** · 2026-10-27 17:31:04

```
{"url": "https://www.biorxiv.org/content/10.1101/2025.06.12.659183v1", "prompt": "Give title, authors, DOI, what ErePOC is, representation, comparison metric, runtime, code URL, published venue."}
```


**← tool result**

```
- **Title:** Deciphering DEL Pocket Patterns through Contrastive Learning
- **Authors:** Wenyi Zhang, Yuxing Wang, Rui Zhan, Runtong Qian, Qi Hu, Jing Huang
- **DOI:** 10.1101/2025.06.12.659183
- **What ErePOC is:** A pocket representation model that uses contrastive learning on "ESM-2 embeddings" to represent protein binding pockets.
- **Representation:** It captures "both structural and functional features of binding pockets," producing high-dimensional embeddings. The page also describes analyzing these alongside low-dimensional physicochemical properties.
- **Comparison metric:** Not stated. The page reports 98% precision on downstream classification tasks but does not name the similarity or comparison metric used for pocket comparison.
- **Runtime:** Not stated.
- **Code URL:** Not provided in the content.
- **Published venue:** Not peer-reviewed or published in a journal according to this page. It is a bioRxiv preprint (version 1), posted June 17, 2025.
```


**← tool result**

```
- **Title:** Mapping the space of protein binding sites with sequence-based protein language models
- **Authors:** Tuğçe Oruç, Maria Kadukova, Thomas G Davies, Marcel Verdonk, Carl Poelking
- **Journal and year:** *Bioinformatics*, 2025 (published June 27, vol. 41, issue 6, article btaf284)
- **DOI:** 10.1093/bioinformatics/btaf284
- **What EPoCS stands for:** ESM-driven Pocket Cross-Similarity
- **Pocket representation:** The authors use the 3B-parameter ESM-2 model to generate an embedding for each residue in a protein sequence. These embeddings are mapped onto an experimental 3D protein–ligand complex. A "radially truncated Voronoi tessellation" around the ligand atoms identifies the surface residues that line the pocket. Mean pooling of those residues' embeddings gives the pocket's EPoCS vector, and pocket similarity is the Euclidean distance between vectors.
- **Runtime numbers:** The article does not report specific timings. It describes EPoCS as alignment-free and computationally cheap, and contrasts it with the costly brute-force use of APoc.
- **Code URL:** https://github.com/tugceoruc/epocs
- **Applied to AlphaFold models:** Not covered. The article uses experimental complexes. It mentions a pseudo-ligand approach for nonliganded sites but says this is not explored in the study.
- **ProSPECCTs benchmark results:** Not reported. ProSPECCTs appears only in the reference list. The article's own benchmarks compare EPoCS with APoc and sequence distance, and they evaluate
… [168 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:18

```
{"query": "SiteMine binding site similarity search large scale", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:18

```
{"query": "POEM subpocket similarity method binding site", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:19

```
{"query": "metal binding site comparison alignment tool ICP AlphaFold metal sites search", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:20

```
{"query": "SiteMatcher binding site comparison", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:20

```
{"query": "spherical convolutional neural network protein binding pocket classification similarity", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "SiteMatcher binding site comparison"

Links: [{"title":"PocketMatch: A new algorithm to compare binding sites in protein structures","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2639437/"},{"title":"A benchmark driven guide to binding site comparison: An exhaustive evaluation using tailor-made data sets (ProSPECCTs)","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6224041/"},{"title":"eprints.iisc.ac.in","url":"https://eprints.iisc.ac.in/19653"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/313615"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2639437"},{"title":"PocketMatch: a new algorithm to compare binding sites in protein structures","url":"https://repository.ias.ac.in/112789"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/track/pdf/10.1186/1471-2105-9-543"},{"title":"A benchmark driven guide to binding site comparison: an exhaustive evaluation using tailor-made data sets (ProSPECCTs)","url":"https://eldorado.tu-dortmund.de/items/1e566b9f-6622-423f-813d-163cb81ff14b"},{"title":"A benchmark driven guide to binding site comparison: an exhaustive evaluation using tailor-made data sets (ProSPECCTs)","url":"https://eldorado.tu-dortmund.de/items/1e566b9f-6622-423f-813d-163cb81ff14b/full"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/60994216"}]

The search didn't turn up anything on a tool called "SiteMatcher." The results cover bind
… [1,074 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "SiteMine binding site similarity search large scale"

Links: [{"title":"New Paper: SiteMine: Large-scale binding site similarity searching in protein structure databases","url":"https://www.zbh.uni-hamburg.de/forschung/amd/news/new-paper-site-mine.html"},{"title":"DOI: 10.1002/ardp.202300661 ISSN: 0365-6233","url":"https://www.citedrive.com/en/discovery/sitemine-largescale-binding-site-similarity-searching-in-protein-structure-databases/"},{"title":"Journal Article PUBDB-2024-01661","url":"https://bib-pubdb1.desy.de/record/606867"},{"title":"www.zbh.uni-hamburg.de","url":"https://www.zbh.uni-hamburg.de/forschung/amd/software/sitemine.html"},{"title":"TY  - JOUR","url":"https://bib-pubdb1.desy.de/record/606867/export/hr?ln=en"},{"title":"Chrome Extension","url":"https://cn.aminer.org/pub/65c7e486939a5f40829acef0/sitemine-large-scale-binding-site-similarity-searching-in-protein-structure-databases"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/track/pdf/10.1186/1471-2105-11-47"},{"title":"link.springer.com","url":"https://link.springer.com/article/10.1186/1471-2105-11-47"},{"title":"Show simple item record","url":"https://dspace.cuni.cz/handle/20.500.11956/191299?show=full"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3098077"}]

SiteMine is a 2024 tool from the Rarey group at Universität Hamburg, described in a paper in *Archiv der Pharmazie* (DOI 10.1002/ard
… [1,393 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "metal binding site comparison alignment tool ICP AlphaFold metal sites search"

Links: [{"title":"Identification of Iron-Sulfur (Fe-S) and Zn-binding Sites Within Proteomes Predicted by DeepMind’s AlphaFold2 Program Dramatically Expands the Metalloproteome","url":"https://www.biorxiv.org/content/10.1101/2021.10.08.463726.full.pdf"},{"title":"Benchmarking Zinc-Binding Site Predictors: A Comparative Analysis of Structure-Based Approaches","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12117554/"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2021.10.08.463726v1.full.pdf+html"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2021.10.08.463726v1.full.pdf"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC12117554"},{"title":"Journal article","url":"https://iro.uiowa.edu/esploro/outputs/journalArticle/Identification-of-Iron-Sulfur-Fe-S-Cluster-and/9984288722002771"},{"title":"Computational Biology Labortory, National Yang Ming Chiao Tung University","url":"https://combio.life.nctu.edu.tw/MIB2/introduction"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10630175"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/49312011"},{"title":"academic.oup.com","url":"https://academic.oup.com/bioinformatics/article/39/11/btad653/7333116"}]

I ran one search. It didn't turn up anything on ICP specifically, but it did surface several too
… [1,691 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "spherical convolutional neural network protein binding pocket classification similarity"

Links: [{"title":"Classification of Protein-Binding Sites Using a Spherical Convolutional Neural Network","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9709917/"},{"title":"DeeplyTough: Learning Structural Comparison of Protein Binding Sites","url":"https://www.biorxiv.org/content/10.1101/600304.full.pdf"},{"title":"DeepDrug3D: Classification of ligand-binding pockets in proteins with a convolutional neural network","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6375647/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC9709917"},{"title":"UCL Discovery Stage","url":"https://discovery-pp.ucl.ac.uk/id/eprint/10159317"},{"title":"Current Medicinal Chemistry","url":"https://www.eurekaselect.com/227877/article"},{"title":"Current Medicinal Chemistry","url":"https://www.benthamscience.com/article/139095"},{"title":"DeepDrug3D: Classification of ligand-binding pockets in proteins with a convolutional neural network","url":"https://paperswithcode.com/paper/deepdrug3d-classification-of-ligand-binding"},{"title":"repository.lsu.edu","url":"https://repository.lsu.edu/eecs_pubs/1439"},{"title":"DeeplyTough: Learning Structural Comparison of Protein Binding Sites","url":"https://cs.paperswithcode.com/paper/deeplytough-learning-structural-comparison-of"}]

The main match is a 2022 paper, Scott, Gu, and Chan, in the *Journal of 
… [1,431 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "POEM subpocket similarity method binding site"

Links: [{"title":"SCR 006109","url":"https://scicrunch.org/resolver/SCR_006109"},{"title":"lab.drugdesign.unistra.fr","url":"https://lab.drugdesign.unistra.fr/tags/algorithms/"},{"title":"pubmed.ncbi.nlm.nih.gov","url":"https://pubmed.ncbi.nlm.nih.gov/20100327"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/313615"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC4383952"},{"title":"BMC Bioinformatics (Jan 2010)","url":"https://doaj.org/article/b7bc7873e47844efba95dca581977a56"},{"title":"Browse views: by Year, by Function, by GLF, by Subfunction, by Conference, by Journal","url":"https://oak.novartis.com/8454/"},{"title":"pdf&i=rrid:scr 006109","url":"https://dknet.org/data/record/nlx_144509-1/SCR_006109/resolver/pdf&i=rrid:scr_006109"},{"title":"SCR 006109","url":"https://rrid.site/resolver/SCR_006109"},{"title":"Searching the RRID Resource Information Network","url":"https://rrid.site/data/record/nlx_144509-1/SCR_006109/resolver"}]

The search didn't return much on POEM itself. The only POEM-specific hit is a lab page that describes it as a generic hit identification method (POEM) for difficult targets of known three-dimensional structure, applied to the WDR domain of LRRK2 in a paper titled "Subpocket Similarity-Based Hit Identification for Challenging Targets." I couldn't find details of how POEM scores binding-site similarity or defines subpockets.

The
… [1,048 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:30

```
{"query": "\"Subpocket Similarity-Based Hit Identification for Challenging Targets\" POEM Rognan", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:30

```
{"query": "\"MetalSiteHunter\"", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:31

```
{"query": "GraphSite binding site graph neural network pocket similarity", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:32

```
{"query": "KRIPO pharmacophore fingerprint binding site similarity Wood 2012 kripodb", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:32

```
{"query": "KiSSim kinase structural signature fingerprint Sydow 2022 JCIM", "mode": "standard"}
```


**← tool result**

```
Web search results for query: ""MetalSiteHunter""

Links: [{"title":"metalinjection.net","url":"https://metalinjection.net/?p=15611"},{"title":"MetalSite Headed For Scrap Heap?","url":"https://www.informationweek.com/it-leadership/metalsite-headed-for-scrap-heap-"},{"title":"Hunter process","url":"https://en.wikipedia.org/wiki/Hunter_process"},{"title":"Content area","url":"https://www.proquest.com/docview/198510358"},{"title":"nih.gov","url":"https://pubmed.ncbi.nlm.nih.gov/24699831"},{"title":"the metal detektor real time multi distro search tool","url":"https://metalinjection.net/around-the-interwebs/the-metal-detektor-real-time-multi-distro-search-tool"},{"title":"Online Scrap Market Grows From MetalSite","url":"https://www.industryweek.com/archive/article/21951082/online-scrap-market-grows-from-metalsite"},{"title":"academic.oup.com","url":"https://academic.oup.com/bib/article/23/6/bbac444/6770088"},{"title":"MetalSite Launches Electronic News Service","url":"https://www.writerswrite.com/metalsite-launches-electronic-news-service-10061998388"},{"title":"- Preview Available","url":"https://www.proquest.com/docview/214459026"}]

The search found no results for "MetalSiteHunter" as a named product, service, or project. The results that come closest are about different things:

- **The Metal Detektor:** A site that searches many metal record distributors at once. It gathers most of these webstores into one common place, and it is a possible match if the name was a shortened 
… [614 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: ""Subpocket Similarity-Based Hit Identification for Challenging Targets" POEM Rognan"

Links: [{"title":"2024 eguida","url":"https://lab.drugdesign.unistra.fr/publications/2024_eguida/"},{"title":"rognan d","url":"https://lab.drugdesign.unistra.fr/authors/rognan-d."},{"title":"www.thesgc.org","url":"https://www.thesgc.org/pubmed/38916159"},{"title":"WD40 Repeats","url":"https://lab.drugdesign.unistra.fr/tags/wd40-repeats/"},{"title":"li f","url":"https://lab.drugdesign.unistra.fr/authors/li-f."},{"title":"lab.drugdesign.unistra.fr","url":"https://lab.drugdesign.unistra.fr/tags/algorithms/"},{"title":"dblp.org","url":"https://dblp.org/pid/24/6670"},{"title":"Challenge #1","url":"https://cache-challenge.org/challenges/app/61f958f1542be"},{"title":"api.openalex.org","url":"https://api.openalex.org/works/doi:10.1021%2FACS.JCIM.4C00601"},{"title":"Binding Sites","url":"https://lab.drugdesign.unistra.fr/tags/binding-sites/"}]

The paper is by Eguida, Bret, Sindt, and others, with Rognan as the last author. It appeared in *Journal of Chemical Information and Modeling* in 2024 (vol. 64, issue 13, pp. 5344–5355), DOI 10.1021/acs.jcim.4c00601.

The method, POEM (Pocket Oriented Elaboration of Molecules), first aligns known fragment-bound subpockets to the target cavity using point cloud registration. It then places the seed fragments in the cavity and links connectable atoms with a deep generative linker to enumerate full ligands. When applied to the WD40 
… [506 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "GraphSite binding site graph neural network pocket similarity"

Links: [{"title":"GraphSite: Ligand Binding Site Classification with Deep Graph Learning","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9405584/"},{"title":"Graphsite: Ligand-binding site classification using Deep Graph Neural Network","url":"https://www.biorxiv.org/content/10.1101/2021.12.06.471420.full.pdf"},{"title":"Graph Representation Learning for Interactive Biomolecule Systems","url":"https://arxiv.org/pdf/2304.02656"},{"title":"GraphSite: Ligand Binding Site Classification with Deep Graph Learning","url":"https://repository.lsu.edu/eecs_pubs/1443"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC9405584"},{"title":"Graphsite classifier","url":"https://github.com/shiwentao00/Graphsite-classifier"},{"title":"www.frontiersin.org","url":"https://www.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2022.837715/pdf"},{"title":"www.ijcai.org","url":"https://www.ijcai.org/proceedings/2026/0610.pdf"},{"title":"digital.lib.washington.edu","url":"https://digital.lib.washington.edu/researchworks/bitstreams/88f27ccc-a0e2-4496-b840-b0d1590ea89d/download"},{"title":"EquiPocket: an E(3)-Equivariant Geometric Graph Neural Network for Ligand Binding Site Prediction","url":"https://ar5iv.labs.arxiv.org/html/2302.12177"}]

The search turned up the GraphSite paper, but it describes a classifier rather than a pocket-similarity tool.

- **What it 
… [1,665 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "KRIPO pharmacophore fingerprint binding site similarity Wood 2012 kripodb"

Links: [{"title":"KRIPO – a structure-based pharmacophores approach explains polypharmacological effects","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3980168/"},{"title":"science.ecosyste.ms","url":"https://science.ecosyste.ms/projects/21323"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3980168"},{"title":"cmdc201700754 fig 0006","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC5900740/figure/cmdc201700754-fig-0006"},{"title":"science.ecosyste.ms","url":"https://science.ecosyste.ms/projects/22125"},{"title":"Charting the Space of Binding-Site Architectures in Proteins: A Large-Scale Analysis","url":"https://gepris.dfg.de/gepris/projekt/170851976/ergebnisse"},{"title":"Published March 28, 2018","url":"https://zenodo.org/records/1209217"},{"title":"science.ecosyste.ms","url":"https://science.ecosyste.ms/api/v1/projects/21323"},{"title":"Incremental update¶","url":"https://kripodb.readthedocs.io/en/latest/incremental-update.html"},{"title":"Category containing Kripo nodes","url":"https://nodepit.com/category/community/3d-e-chem/kripodb"}]

The search turned up the Wood et al. 2012 paper, the KRIPO method, and the kripodb software.

- **The 2012 paper:** Wood, de Vlieg, Wagener and Ritschel published "Pharmacophore Fingerprint-Based Approach to Binding Site Subpocket Similarity and Its Application to Bioisostere Replacement" in J Ch
… [1,728 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "KiSSim kinase structural signature fingerprint Sydow 2022 JCIM"

Links: [{"title":"bioinformaticshome.com","url":"https://bioinformaticshome.com/db/tool/kissim"},{"title":"KiSSim: Predicting off-targets from structural similarities in the kinome","url":"https://test01.ku.dk/:obvius/pureproxy/3974268/en/datasets/kissim-predicting-off-targets-from-structural-similarities-in-the"},{"title":"bioinformaticshome.com","url":"https://bioinformaticshome.com/db/tool/KiSSim"},{"title":"T025 · Kinase similarity: Kinase pocket (KiSSim fingerprint)¶","url":"https://projects.volkamerlab.org/teachopencadd/talktorials/T025_kinase_similarity_kissim.html"},{"title":"kissim chemrxiv","url":"https://volkamerlab.org/2021/12/kissim-chemrxiv/"},{"title":"www.cambridge.org","url":"https://www.cambridge.org/engage/coe/article-details/61b73ba902d90d059c610e9b"},{"title":"Kinase Similarity Assessment Pipeline for Off-Target Prediction [Article v1.0]","url":"https://livecomsjournal.org/index.php/livecoms/article/view/v3i1e1599"},{"title":"chemrxiv.org","url":"https://chemrxiv.org/engage/chemrxiv/article-details/61b73ba902d90d059c610e9b"},{"title":"client.prod.orp.cambridge.org","url":"https://client.prod.orp.cambridge.org/engage/chemrxiv/article-details/61b73ba902d90d059c610e9b"},{"title":"Subscribe in a reader","url":"https://cambridgemedchemconsulting.com/news/index_files/category-kinase-inhibitors.html"}]

The search confirmed the core publication and what the fingerprin
… [1,598 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:44

```
{"query": "\"SiteContext\" OR \"Siteomix\" protein binding site", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:45

```
{"query": "ACP4 pocket comparison protein binding site", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:45

```
{"query": "FUSED binding site similarity fused descriptor pocket", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:46

```
{"query": "DMPPS protein pocket similarity", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:47

```
{"query": "PDBspheres binding site library structural alignment Zemla", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "ACP4 pocket comparison protein binding site"

Links: [{"title":"A Comprehensive Survey of Small-Molecule Binding Pockets in Proteins","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3812058/"},{"title":"PocketMatch: A new algorithm to compare binding sites in protein structures","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2639437/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3582269"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/313615"},{"title":"nih.gov","url":"https://pubmed.ncbi.nlm.nih.gov/23335017"},{"title":"Next Article in Journal","url":"https://www.mdpi.com/1422-0067/23/20/12462/htm"},{"title":"Center for the Study of Systems Biology","url":"https://sites.gatech.edu/cssb/apoc"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2639437"},{"title":"PocketMatch: a new algorithm to compare binding sites in protein structures","url":"https://repository.ias.ac.in/112789"},{"title":"eprints.iisc.ac.in","url":"https://eprints.iisc.ac.in/19653"}]

The search didn't return anything specific to ACP4 (acyl carrier protein 4, or whatever ACP4 refers to in your project). The results cover general pocket-comparison methods, which may still be useful.

- **APoc** is a pocket-comparison tool that scores pocket similarity with a PS-score. It is a sequence order-independent, structural comparison method for large-scale analysis of protein pockets. It is freely availab
… [672 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "PDBspheres binding site library structural alignment Zemla"

Links: [{"title":"PDBspheres - a method for finding 3D similarities in local regions in proteins","url":"https://www.biorxiv.org/content/10.1101/2022.01.04.474934.full.pdf"},{"title":"PDBspheres: a method for finding 3D similarities in local regions in proteins","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9549786/"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2022.01.04.474934v2.full.pdf+html"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2022.01.04.474934v1.full.pdf"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2022.01.04.474934v2.full.pdf"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC9549786"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2022.01.04.474934v1.full.pdf+html"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2022.01.04.474934v2"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2022.01.04.474934v1"},{"title":"An official website of the United States government","url":"https://software.llnl.gov/news/2022/07/29/pdbspheres-new/"}]

PDBspheres is a structure-based method by Adam Zemla and colleagues (Lawrence Livermore National Laboratory) for finding and evaluating local 3D similarities in protein binding regions. It was published in NAR Genomics and Bioinformatics 
… [1,509 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "DMPPS protein pocket similarity"

Links: [{"title":"Estimating the Similarity between Protein Pockets","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9604425/"},{"title":"DeeplyTough: Learning Structural Comparison of Protein Binding Sites","url":"https://www.biorxiv.org/content/10.1101/600304.full.pdf"},{"title":"A new method for rapid comparison of protein binding pockets by capturing spatial distributions","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3980086/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3582269"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC9604425"},{"title":"nih.gov","url":"https://pubmed.ncbi.nlm.nih.gov/23335017"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/counter/pdf/10.1186/1471-2105-11-99.pdf"},{"title":"2022 eguida 1","url":"https://lab.drugdesign.unistra.fr/publications/2022_eguida_1/"},{"title":"link.springer.com","url":"https://link.springer.com/doi/10.1186/1471-2105-11-99"},{"title":"aporc.org","url":"https://www.aporc.org/LNOR/7/OSB2007F24.pdf"}]

The search didn't turn up anything specific to DMPPS. The results cover protein pocket similarity in general, so I can't confirm what DMPPS refers to or whether it has a pocket-similarity analysis.

The general background is useful, though:

- **Pocket similarity is hard to pin down.** One review says similarity is a non-measurable c
… [895 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: ""SiteContext" OR "Siteomix" protein binding site"

Links: [{"title":"Journal article","url":"https://iro.uiowa.edu/esploro/outputs/journalArticle/SiteContext-A-Web-Server-for-Protein/9985152240602771"},{"title":"tintin.cs.uiowa.edu","url":"https://tintin.cs.uiowa.edu/SiteContext/about"},{"title":"Protein Binding Site Mapping","url":"https://creativebiomart.net/protein-binding-site-mapping.htm"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3324516"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2323941"},{"title":"elifesciences.org","url":"https://elifesciences.org/reviewed-preprints/93695v2"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2639300"},{"title":"Predicting small ligand binding sites in proteins using backbone structure","url":"https://eurekamag.com/research/055/100/055100891.php"},{"title":"Please use this identifier to cite or link to this item: http://hdl.handle.net/10397/61679","url":"https://ira.lib.polyu.edu.hk/handle/10397/61679?mode=full"},{"title":"SiteLight: binding-site prediction using phage display libraries","url":"https://pubmed.ncbi.nlm.nih.gov/12824481/"},{"title":"inass.org","url":"https://inass.org/2020/2020123102.pdf"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3017595"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC441612"},{"title":"shephard.
… [1,464 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "FUSED binding site similarity fused descriptor pocket"

Links: [{"title":"PocketPicker: analysis of ligand binding-sites with shape descriptors","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1994066/"},{"title":"Comprehensive detection and characterization of human druggable pockets through novel binding site descriptors","url":"https://www.biorxiv.org/content/10.1101/2024.03.14.584971.full.pdf"},{"title":"Estimating the Similarity between Protein Pockets","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9604425/"},{"title":"Nature Communications (Sep 2024)","url":"https://doaj.org/article/8c11db43ff354f759520de8c28ea0279"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC1994066"},{"title":"Sample records for pocket shape differences","url":"https://www.science.gov/topicpages/p/pocket+shape+differences"},{"title":"comprehensive detection and characterization human druggable pockets through","url":"https://irbbarcelona.org/en/about-us/publications/comprehensive-detection-and-characterization-human-druggable-pockets-through"},{"title":"Pasar al contenido principal","url":"https://irbbarcelona.org/es/about-us/publications/comprehensive-detection-and-characterization-human-druggable-pockets-through"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/313615"},{"title":"PocketPicker: analysis of ligand binding-sites with shape descriptors","url":"https://publikationen.ub.uni-frankfurt.de/frontdoor/index/ind
… [1,603 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:56

```
{"query": "\"LEN-Seek\" OR \"LENSeek\" protein pocket", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:56

```
{"query": "\"GTA-5\" protein pocket graph transformer binding site", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:56

```
{"query": "ECIFP extended connectivity interaction features fingerprint protein ligand", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:57

```
{"query": "RAPMAD rapid pocket matching alignment-free distribution", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:31:57

```
{"query": "TrixP binding site similarity Rarey indexing triplets", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "RAPMAD rapid pocket matching alignment-free distribution"

Links: [{"title":"A new method for rapid comparison of protein binding pockets by capturing spatial distributions","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3980086/"},{"title":"- Poster presentation","url":"https://jcheminf.biomedcentral.com/articles/10.1186/1758-2946-6-S1-P45"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/2303.14994v5"},{"title":"patents.google.com","url":"https://patents.google.com/patent/US6434488"},{"title":"www.lirmm.fr","url":"https://www.lirmm.fr/?p=4746"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/node/101029"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/328740v5"},{"title":"lirmm 02410441","url":"https://hal-lirmm.ccsd.cnrs.fr/lirmm-02410441"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/328740v2.full.txt"},{"title":"We gratefully acknowledge support from","url":"https://export.arxiv.org/abs/2303.14994v3"}]

RAPMAD (Rapid Pocket Matching using Distances) is a method for comparing protein binding pockets, and it was presented as a 2014 conference poster in the *Journal of Cheminformatics*. The search turned up only that poster and its abstract, not a full paper.

- **Method:** Protein binding sites are represented by sets of distance histograms based on specific spatial reference points, which capture how pharmacophore-like "pseudocenters" are distributed inside a cavity. Th
… [977 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: ""LEN-Seek" OR "LENSeek" protein pocket"

Links: [{"title":"Pocket tracking and identification of transient regions","url":"https://trapp.h-its.org/trapp/application/doc/algorithm"},{"title":"MSPocket: an orientation-independent algorithm for the detection of ligand binding pockets","url":"https://fis.tu-dresden.de/portal/de/publications/mspocket(4fcd10d1-5e2f-4453-b549-a796460bfa60).html"},{"title":"Fpocket: an open source platform for ligand pocket detection","url":"https://pubmed.ncbi.nlm.nih.gov/19486540/"},{"title":"durrantlab.pitt.edu","url":"https://durrantlab.pitt.edu/molmoda/docs/structures/pockets/"},{"title":"pocketeer.readthedocs.io","url":"https://pocketeer.readthedocs.io/"},{"title":"Pocket Detection¶","url":"https://enspara.readthedocs.io/en/latest/pocket-detection.html"},{"title":"BMC Bioinformatics (Jun 2009)","url":"https://doaj.org/article/4204d8333ea2418cbfd7a98272efe95a"},{"title":"12.10 Pockets - Protein cavity detection and mapping","url":"https://nova.disfarm.unimi.it/manual/plugins/pockets.htm"},{"title":"Pocket Detection","url":"https://durrantlab.pitt.edu/molmoda/docs/plugins/reference/fpocketweb/"},{"title":"Supported Applications","url":"https://sbgrid.org/software/titles/fpocket"}]

The search didn't turn up anything on "LEN-Seek" or "LENSeek" as a protein pocket method, tool, or target. Neither term appears in the results, so I can't confirm what it refers to. It may be a name I'm not finding, a spelling variant, or
… [918 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "TrixP binding site similarity Rarey indexing triplets"

Links: [{"title":"Iterative optimization in the design of binding proteins","url":"https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6794136"},{"title":"Fast Protein Binding Site","url":"https://core.ac.uk/works/49486739"},{"title":"Protein & Peptide Letters","url":"https://www.benthamscience.com/article/31452"},{"title":"Publication Details","url":"https://fit.vut.cz/research/publication/9773"},{"title":"lexa martinek rudolfova fixed2013","url":"https://www.fi.muni.cz/~lexa/triplex/lexa_martinek_rudolfova_fixed2013.pdf"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3101549/figure/fig2"},{"title":"Závěrečná práce: Juraj Jurčo, učo 173001: Program pre analýzu DNA sekvencií z hľadiska výskytu triplexov","url":"https://is.muni.cz/th/inyt7/"},{"title":"The University of Southampton","url":"https://eprints.soton.ac.uk/475870"},{"title":"A dynamic programming algorithm for identification of triplex-forming sequences","url":"https://www.ibp.cz/cs/vyzkum/oddeleni/biofyzikalni-chemie-a-molekularni-onkologie/publikace/p11195"},{"title":"Publication Details","url":"https://www-dev.fit.vutbr.cz/research/publication/c76462"}]

The search turned up one relevant source. It is a CORE record for a paper introducing TrixP, an index-based method for comparing protein binding sites. TrixP determines binding site similarities based on the comparison of descripto
… [851 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "ECIFP extended connectivity interaction features fingerprint protein ligand"

Links: [{"title":"Proteo-chemometrics interaction fingerprints of protein-ligand complexes predict binding affinity","url":"https://scholars.hkmu.edu.hk/en/publications/proteo-chemometrics-interaction-fingerprints-of-protein-ligand-co/"},{"title":"Proteo-chemometrics interaction fingerprints of protein-ligand complexes predict binding affinity","url":"https://scholars.ln.edu.hk/en/publications/proteo-chemometrics-interaction-fingerprints-of-protein-ligand-co/"},{"title":"oddt package¶","url":"https://oddt.readthedocs.io/en/0.5/rst/oddt.html"},{"title":"proteo chemometrics interaction fingerprints of protein ligand co","url":"https://scholars.cityu.edu.hk/en/publications/proteo-chemometrics-interaction-fingerprints-of-protein-ligand-co/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC6477977"},{"title":"oddt package","url":"https://oddt.readthedocs.io/en/stable/rst/oddt.html"},{"title":"oddt package","url":"https://oddt.readthedocs.io/en/0.4/rst/oddt.html"},{"title":"chemrxiv.org","url":"https://chemrxiv.org/engage/chemrxiv/article-details/60c73d92bb8c1ab17e3d9797"},{"title":"client.prod.orp.cambridge.org","url":"https://client.prod.orp.cambridge.org/engage/chemrxiv/article-details/60c73d92bb8c1ab17e3d9797"},{"title":"Prioritizing virtual screening with interpretable interaction fingerprints","url":"https://preprints.kavlimeetings.org/2
… [1,724 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: ""GTA-5" protein pocket graph transformer binding site"

Links: [{"title":"Protein ligand binding site prediction using graph transformer neural network","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11302905/"},{"title":"AlphaFold2-aware protein-DNA binding site prediction using graph transformer","url":"https://www.biorxiv.org/content/10.1101/2021.08.25.457661.full.pdf"},{"title":"Efficient Generation of Protein Pockets with PocketGen","url":"https://www.biorxiv.org/content/10.1101/2024.02.25.581968.full.pdf"},{"title":"DynamicGT: a dynamic-aware geometric transformer model to predict protein binding interfaces in flexible and disordered regions","url":"https://www.biorxiv.org/content/10.1101/2025.03.04.641377.full.pdf"},{"title":"skip to main content","url":"https://par.nsf.gov/biblio/10572215"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC11684089"},{"title":"Efficient Generation of Protein Pockets with PocketGen","url":"https://zitniklab.hms.harvard.edu/projects/PocketGen"},{"title":"par.nsf.gov","url":"https://par.nsf.gov/servlets/purl/10572215"},{"title":"Research News","url":"https://english.cas.cn/newsroom/news--archives/2024/research-news/202412/t20241227_1130557.shtml"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10925136.2"}]

The search didn't turn up anything about "GTA-5" specifically. None of the results mention that term, so it may be a typo, an internal
… [1,752 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:07

```
{"query": "\"Fast protein binding site comparison via an index-based screening technology\" von Behren doi", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:08

```
{"query": "PocketShape kinase pocket comparison Eguida Rognan 2022", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:08

```
{"query": "PSIM pocket similarity Rognan volsite Shaper benchmark", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:09

```
{"query": "BioGPS binding site comparison GRID molecular interaction fields Siragusa Cross 2015", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:32:10

```
{"query": "Grim interaction pattern matching Desaphy Rognan 2013 binding site", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "PocketShape kinase pocket comparison Eguida Rognan 2022"

Links: [{"title":"Next Article in Journal","url":"https://www.mdpi.com/1422-0067/23/20/12462/review_report"},{"title":"IDEAS home Printed from https://ideas.repec.org/a/plo/pone00/0189147.html","url":"https://ideas.repec.org/a/plo/pone00/0189147.html"},{"title":"ri.conicet.gov.ar","url":"https://ri.conicet.gov.ar/handle/11336/41443"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3248393"},{"title":"volkamerlab.org","url":"https://volkamerlab.org/projects/kissim/"},{"title":"nih.gov","url":"https://pubmed.ncbi.nlm.nih.gov/23335017"},{"title":"kissim chemrxiv","url":"https://volkamerlab.org/2021/12/kissim-chemrxiv/"},{"title":"Mostrar el registro sencillo del ítem","url":"https://ri.conicet.gov.ar/handle/11336/41443?show=full"},{"title":"Welcome to the kissim documentation","url":"https://kissim.readthedocs.io/"},{"title":"rcsb.org","url":"https://rcsb.org/structure/3fjq"}]

I didn't find any source mentioning "PocketShape." The closest match is the Eguida and Rognan 2022 paper, "Estimating the Similarity between Protein Pockets," published in the *International Journal of Molecular Sciences* (23(20), 12462). It is a review article, and the search result shows only its peer-review record, not the full text. The reviewers say the authors evaluate published results and state the advantages and shortcomings of widely used computational methods for pocket detec
… [887 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "Grim interaction pattern matching Desaphy Rognan 2013 binding site"

Links: [{"title":"Encoding Protein–Ligand Interaction Patterns in Fingerprints and Graphs","url":"https://lab.drugdesign.unistra.fr/publications/2013_desaphy/"},{"title":"10.1007%2FS10822 016 9930 3","url":"https://unpaywall.org/10.1007%2FS10822-016-9930-3"},{"title":"P11 Gomes","url":"https://infochim.chimie.unistra.fr/CS3_2018/PosterAbstracts/P11-Gomes.pdf"},{"title":"P11 Gomes","url":"https://infochim.chimie.unistra.fr/Fr-Jp_2018/P11_Gomes.pdf"},{"title":"dblp.uni-trier.de","url":"https://dblp.uni-trier.de/pid/141/2400.html"},{"title":"sc-PDB: a 3D-database of ligandable binding sites—10 years on","url":"https://lab.drugdesign.unistra.fr/publications/2015_desaphy/"},{"title":"Docking pose selection by interaction pattern graph similarity: application to the D3R grand challenge 2015","url":"https://lab.drugdesign.unistra.fr/publications/2016_slynko/"},{"title":"Ranking docking poses by graph matching of protein–ligand interactions: lessons learned from the D3R Grand Challenge 2","url":"https://lab.drugdesign.unistra.fr/publications/2018_da-silva-figueiredo-celestino-gomes"},{"title":"s12859 020 3347 7","url":"https://bmcbioinformatics.biomedcentral.com/track/pdf/10.1186/s12859-020-3347-7"},{"title":"s10822 017 0046 1","url":"https://springerlink.bibliotecabuap.elogim.com/10.1007/s10822-017-0046-1"}]

The 2013 paper is Desaphy, Raimbaud, Ducrot and Rognan, "Encoding Protein–Li
… [1,114 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: ""Fast protein binding site comparison via an index-based screening technology" von Behren doi"

Links: [{"title":"PocketMatch: A new algorithm to compare binding sites in protein structures","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2639437/"},{"title":"Fast Protein Binding Site","url":"https://core.ac.uk/works/49486739"},{"title":"bibsonomy.org","url":"https://bibsonomy.org/bibtex/4ffe409b191895c842a8ffa22d92a676"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2639437"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/313615"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/track/pdf/10.1186/1471-2105-9-543"},{"title":"PocketMatch: a new algorithm to compare binding sites in protein structures","url":"https://repository.ias.ac.in/112789"},{"title":"Methods for the Efficient Comparison of Protein Binding Sites and for the Assessment of Protein-Ligand Complexes","url":"https://archiv.ub.uni-marburg.de/ubfind/Record/urn:nbn:de:hebis:04-z2015-0384?sid=653123"},{"title":"eprints.iisc.ac.in","url":"https://eprints.iisc.ac.in/19653"},{"title":"Improvement of Methods for the Comparison of Protein Binding Sites","url":"https://www.hkhlr.de/de/node/299"}]

The paper is "Fast Protein Binding Site Comparison via an Index-Based Screening Technology" by Mathias M. von Behren, Andrea Volkamer, Angela M. Henzler, Karen Schomburg, Sascha Urbaczek, and Matthias Rar
… [688 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "BioGPS binding site comparison GRID molecular interaction fields Siragusa Cross 2015"

Links: [{"title":"katalog.lib.cas.cz","url":"https://katalog.lib.cas.cz/KNAV/EdsRecord/edb,96645650"},{"title":"research.unipg.it","url":"https://research.unipg.it/handle/11391/1238697"},{"title":"research.unipg.it","url":"https://research.unipg.it/handle/11391/1334116"},{"title":"IsoMIF Finder: online detection of binding site molecular interaction field similarities","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4743630/"},{"title":"CS3 2014 Cruciani","url":"https://infochim.chimie.unistra.fr/CS3_2014/Slides/CS3_2014_Cruciani.pdf"},{"title":"CS3 2014 OP Cruciani","url":"https://infochim.chimie.unistra.fr/CS3_2014/OralAbstracts/CS3_2014_OP_Cruciani.pdf"},{"title":"moldiscovery.com","url":"https://moldiscovery.com/software/biogps/"},{"title":"biogps 2201 released","url":"https://www.moldiscovery.com/blog/biogps-2201-released/"},{"title":"www.scitepress.org","url":"https://www.scitepress.org/Papers/2011/36374/36374.pdf"},{"title":"Journal of Proteomics & Bioinformatics","url":"https://www.longdom.org/proceedings/navigating-the-3d-biological-space--the-biogps-approach-29177.html"}]

The search returned several sources on BioGPS, though none confirms the exact "Siragusa, Cross, 2015" author combination you named.

- **Core method:** BioGPS is a semi-automated method for comparing and clustering protein pockets. It combines GRID molecular interaction fields 
… [1,134 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "PSIM pocket similarity Rognan volsite Shaper benchmark"

Links: [{"title":"A new protein binding pocket similarity measure based on comparison of 3D atom clouds: application to ligand prediction","url":"https://arxiv.org/pdf/0907.1531"},{"title":"Center for the Study of Systems Biology","url":"https://sites.gatech.edu/cssb/apoc"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/313615"},{"title":"nih.gov","url":"https://pubmed.ncbi.nlm.nih.gov/23335017"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3582269"},{"title":"biophys.jp","url":"https://biophys.jp/news/lib/newsshow.php/3425"},{"title":"- Poster presentation","url":"https://jcheminf.biomedcentral.com/articles/10.1186/1758-2946-6-S1-P45"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/counter/pdf/10.1186/1471-2105-11-99.pdf"},{"title":"PocketMatch: a new algorithm to compare binding sites in protein structures","url":"https://repository.ias.ac.in/112789"},{"title":"Biophysics and Physicobiology","url":"https://www.jstage.jst.go.jp/article/biophysico/13/0/13_139/_article"}]

The search did not return any sources on PSIM, Rognan's work, VolSite, or Shaper, so I can't confirm a benchmark comparing them. The results covered related pocket-comparison methods:

- **Poisson index (PI):** Pocket alignment followed by counting overlapping atoms is the basis of the Poisson index model, which is one of the exis
… [1,323 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:32:35

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad 2>/dev/null || mkdir -p /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\ncat > /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/cr.py <<'EOF'\nimport sys, json, urllib.request, urllib.parse\nfor q in sys.stdin:\n    q=q.strip()\n    if not q: continue\n    url=\"https://api.crossref.org/works?rows=2&select=DOI,title,container-title,issued,author&query.bibliographic=\"+urllib.parse.quote(q)\n    try:\n        d=json.load(urllib.request.urlopen(url,timeout=30))\n        for it in d['message']['items']:\n            a=it.get('author',[{}])[0].get('family','?') if it.get('author') else '?'\n            print(f\"{q[:40]:40s} | {it['DOI']} | {it.get('title',[''])[0][:90]} | {(it.get('container-title') or [''])[0][:40]} | {it['issued']['date-parts'][0][0]} | {a}\")\n    except Exception as e:\n        print(q, \"ERR\", e)\nEOF\ncat > /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad/q1.txt <<'EOF'\nFast Protein Binding Site Comparison via an Index-Based Screening Technology von Behren\nSiteEngines: recognition and comparison of binding sites and protein-protein interfaces Shulman-Peleg\nRecognition of functional sites in protein structures Shulman-Peleg Nussin
… [2,340 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Fast Protein Binding Site Comparison via | 10.1021/ci300469h | Fast Protein Binding Site Comparison via an Index-Based Screening Technology | Journal of Chemical Information and Mode | 2013 | von Behren
Fast Protein Binding Site Comparison via | 10.1002/prot.26176/v1/review2 | Review for "A fast protein binding site comparison algorithm for proteome‐wide protein fun |  | 2021 | ?
SiteEngines: recognition and comparison  | 10.1093/nar/gki482 | SiteEngines: recognition and comparison of binding sites and protein-protein interfaces | Nucleic Acids Research | 2005 | Shulman-Peleg
SiteEngines: recognition and comparison  | 10.1016/j.jmb.2004.04.012 | Recognition of Functional Sites in Protein Structures | Journal of Molecular Biology | 2004 | Shulman-Peleg
Recognition of functional sites in prote | 10.1016/j.jmb.2004.04.012 | Recognition of Functional Sites in Protein Structures | Journal of Molecular Biology | 2004 | Shulman-Peleg
Recognition of functional sites in prote | 10.1093/nar/gki482 | SiteEngines: recognition and comparison of binding sites and protein-protein interfaces | Nucleic Acids Research | 2005 | Shulman-Peleg
I2I-SiteEngine protein-protein interface | 10.1186/1741-7007-5-43 | Spatial chemical conservation of hot spot interactions in protein-protein complexes | BMC Biology | 2007 | Shulman-Peleg
I2I-SiteEngine protein-protein interface | 10.1093/nar/gki482 | SiteEngines: recognition and comparison of binding sites and protein-protein interfaces | Nucleic Acids Re
… [8,933 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:33:11

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\nsed -i 's/^    q=q.strip()/    import time; time.sleep(1.5); q=q.strip()/' cr.py\ncat > q2.txt <<'EOF'\nA fast protein binding site comparison algorithm for proteome-wide protein function prediction\nSiteAlign measuring cavity similarity Schalon Rognan 2008 Proteins\nSMAP detecting evolutionary relationships across existing fold space sequence order-independent profile-profile alignments Xie Bourne\nUsing multiple microenvironments to find similar ligand-binding sites application to kinase inhibitor binding Liu Altman\nBioGPS navigating biological space to predict polypharmacology off-targeting selectivity Siragusa\nLabelHash Moll Kavraki BMC Bioinformatics matching structural motifs\nG-LoSA graph-based local structure alignment ligand binding sites Lee Im 2016\nProBiS-Dock hybrid multitemplate homology flexible docking algorithm\nDeeplyTough Simonovsky Meyers Journal of Chemical Information and Modeling\nDrugCLIP contrastive protein-molecule representation learning for virtual screening\nDeep contrastive learning enables genome-wide virtual screening\nMaSIF deciphering interaction fingerprints from protein molecular surfaces using geometric deep learning\nPocketVec inverse virtual screening pocket descriptors\nSite2Vec reference frame invariant vector embedding protein-ligand binding sites\nFuzCav fuzzy cavity fingerprint binding site comparison
… [472 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
A fast protein binding site comparison a | 10.1002/prot.26176/v2/review1 | Review for "A fast protein binding site comparison algorithm for proteome‐wide protein fun |  | 2021 | ?
A fast protein binding site comparison a | 10.1002/prot.26176/v1/review2 | Review for "A fast protein binding site comparison algorithm for proteome‐wide protein fun |  | 2021 | ?
SiteAlign measuring cavity similarity Sc | 10.2174/157340908785747401 | How to Measure the Similarity Between Protein Ligand-Binding Sites? | Current Computer Aided-Drug Design | 2008 | Kellenberger
SiteAlign measuring cavity similarity Sc | 10.1002/prot.21858 | A simple and fuzzy method to align and compare druggable ligand‐binding sites | Proteins: Structure, Function, and Bioin | 2008 | Schalon
SMAP detecting evolutionary relationship | 10.1073/pnas.0704422105 | Detecting evolutionary relationships across existing fold space, using sequence order-inde | Proceedings of the National Academy of S | 2008 | Xie
SMAP detecting evolutionary relationship | 10.1101/2022.07.29.501943 | Deep Generative Models of Protein Structure Uncover Distant Relationships Across a Continu |  | 2022 | Draizen
Using multiple microenvironments to find | 10.1371/journal.pcbi.1002326 | Using Multiple Microenvironments to Find Similar Ligand-Binding Sites: Application to Kina | PLoS Computational Biology | 2011 | Liu
Using multiple microenvironments to find | 10.1021/acsabm.2c01079.s001 | Identifying Potential Ligand Binding Sites on Glycogen Syntha
… [6,215 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:04

```
{"query": "\"A fast protein binding site comparison algorithm for proteome-wide protein function prediction\" Proteins 2021", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:05

```
{"query": "PoSSuM pocket similarity search multiple sketches Ito Tomii all-against-all PDB pairs", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:05

```
{"query": "persistent homology protein binding pocket similarity comparison", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:06

```
{"query": "optimal transport Wasserstein protein binding site comparison point cloud", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:06

```
{"query": "PocketGraph binding pocket graph comparison", "mode": "standard"}
```


**← tool result**

```
Web search results for query: ""A fast protein binding site comparison algorithm for proteome-wide protein function prediction" Proteins 2021"

Links: [{"title":"Fast Local Alignment of Protein Pockets (FLAPP): A system-compiled program for large-scale binding site alignment","url":"https://www.biorxiv.org/content/10.1101/2022.07.13.499925.full.pdf"},{"title":"A fast protein binding site comparison algorithm for proteome-wide protein function prediction and drug repurposing","url":"https://pure.ecnu.edu.cn/en/publications/a-fast-protein-binding-site-comparison-algorithm-for-proteome-wid/"},{"title":"Fast Protein Binding Site","url":"https://core.ac.uk/works/49486739"},{"title":"an efficient algorithm for matching protein binding sites for pro 5","url":"https://scholars.ttu.edu/en/publications/an-efficient-algorithm-for-matching-protein-binding-sites-for-pro-5"},{"title":"(A) method to detect important residues using protein binding site comparison단백질의 결합자리 비교를 통한 중요 잔기 탐색 방법","url":"https://koasas.kaist.ac.kr/handle/10203/27135?mode=full"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/track/pdf/10.1186/1471-2105-9-543"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3398928"},{"title":"Journal list menu","url":"https://onlinelibrary-wiley-com-443.webvpn.zafu.edu.cn/toc/10970134/2021/89/11"},{"title":"iisc.ac.in","url":"https://eprints.iisc.ac.in/44982/"},{"title":"PocketAnnotate: towards site
… [1,308 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "PocketGraph binding pocket graph comparison"

Links: [{"title":"A new method for rapid comparison of protein binding pockets by capturing spatial distributions","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3980086/"},{"title":"SpliceBind: Isoform-Aware Prediction of Binding Pocket Druggability","url":"https://arxiv.org/pdf/2606.04020"},{"title":"Analysis of shape, properties and \"druggability\" of protein binding pockets","url":"https://core.ac.uk/works/6091637"},{"title":"PocketGraph : graph representation of binding site volumes","url":"https://publikationen.ub.uni-frankfurt.de/frontdoor/index/index/year/2009/docId/6785"},{"title":"publikationen.ub.uni-frankfurt.de","url":"https://publikationen.ub.uni-frankfurt.de/solrsearch/index/search/searchtype/authorsearch/author/Jan+M.+Kriegl"},{"title":"- Poster presentation","url":"https://jcheminf.biomedcentral.com/articles/10.1186/1758-2946-6-S1-P45"},{"title":"link.springer.com","url":"https://link.springer.com/doi/10.1186/1471-2105-11-99"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/counter/pdf/10.1186/1471-2105-11-99.pdf"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/0907.1531v1.pdf"},{"title":"www.hkhlr.de","url":"https://www.hkhlr.de/node-export/pdf/299"}]

The search turned up one clear match for PocketGraph and several related pocket-comparison methods.

- **PocketGraph itself:** It's a method from a Frankfurt dissertation. It 
… [1,354 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "persistent homology protein binding pocket similarity comparison"

Links: [{"title":"Comparative assessment of strategies to identify similar ligand-binding pockets in proteins","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5845264/"},{"title":"A quantitative structure comparison with persistent similarity","url":"https://arxiv.org/pdf/1707.03572"},{"title":"Estimating the Similarity between Protein Pockets","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9604425/"},{"title":"DeeplyTough: Learning Structural Comparison of Protein Binding Sites","url":"https://www.biorxiv.org/content/10.1101/600304.full.pdf"},{"title":"PocketMatch: A new algorithm to compare binding sites in protein structures","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2639437/"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/313615"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/track/pdf/10.1186/1471-2105-9-543"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3155014"},{"title":"PocketMatch: a new algorithm to compare binding sites in protein structures","url":"https://repository.ias.ac.in/112789"},{"title":"A quantitative structure comparison with persistent similarity","url":"https://ar5iv.labs.arxiv.org/html/1707.03572"}]

The search found one directly relevant persistent-homology paper, but no study that applies it specifically to binding-pocket comparison.

- **P
… [1,519 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "optimal transport Wasserstein protein binding site comparison point cloud"

Links: [{"title":"Slicing Wasserstein Over Wasserstein Via Functional Optimal Transport","url":"https://arxiv.org/pdf/2509.22138"},{"title":"Multiscale guidance of protein structure prediction with heterogeneous cryo-EM data","url":"https://arxiv.org/pdf/2506.04490"},{"title":"UAlberta MMI/ MSB Seminar: Khanh Dao Duc","url":"https://pims.math.ca/events/251103-ummskdd"},{"title":"Auto-WHATMD : Automated Wasserstein-based High-dimensional feature","url":"https://www.alphaxiv.org/abs/2603.14414.md"},{"title":"The Challenge of Comparing Molecular Dynamics Ensembles","url":"https://www.alphaxiv.org/overview/2603.14414"},{"title":"Joint Maud Menten /Math Bio Seminar: Khanh Dao Duc","url":"https://pims.math.ca/events/251103-jmmmbskdd"},{"title":"License: CC BY-NC-ND 4.0","url":"https://arxiv.org/html/2603.14414v1"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC5774846/figure/pcbi.1005929.g003"},{"title":"two sample goodness of fit tests on the flat torus based on wasserstein distance and their relevance","url":"https://www.carmin.tv/fr/video/two-sample-goodness-of-fit-tests-on-the-flat-torus-based-on-wasserstein-distance-and-their-relevance"},{"title":"GDR ISIS - Transport Optimal et Apprentissage Statistique","url":"https://www.carmin.tv/fr/collections/gdr-isis-transport-optimal-et-apprentissage-statistique/video/two-sample-goodness-of-fit-tes
… [2,354 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "PoSSuM pocket similarity search multiple sketches Ito Tomii all-against-all PDB pairs"

Links: [{"title":"Dynamic Similarity Search on Integer Sketches","url":"https://arxiv.org/pdf/2009.11559"},{"title":"PoSSuM v.2.0: data update and a new function for investigating ligand analogs and target proteins of small-molecule drugs","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4383952/"},{"title":"Another Word For It Patrick Durusau on Topic Maps and Semantic Diversity","url":"https://tm.durusau.net/?p=29663"},{"title":"pdf&i=rrid:scr 006109","url":"https://dknet.org/data/record/nlx_144509-1/SCR_006109/resolver/pdf&i=rrid:scr_006109"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC4383952"},{"title":"SCR 006109","url":"https://rrid.site/resolver/SCR_006109"},{"title":"dblp.uni-trier.de","url":"https://dblp.uni-trier.de/pid/00/2749.html"},{"title":"dblp.dagstuhl.de","url":"https://dblp.dagstuhl.de/pid/00/2749.html"},{"title":"20130118 Tomii","url":"https://cbrc3.cbrc.pj.aist.go.jp/ja/education/pdf/20130118-Tomii.pdf"},{"title":"PoSSuMsearch: Fast and sensitive matching of position specific scoring matrices using enhanced suffix arrays","url":"https://dl.gi.de/items/f09ccca6-9233-46bd-acdf-62df3a6a7f5a/full"}]

The search turned up the PoSSuM database and its method, but not the original methods paper's full text, so the details below come from secondary sources.

- **Method:** PoSSuM stands for Pocket Similarity S
… [1,678 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:34:20

```
{"url": "https://pure.ecnu.edu.cn/en/publications/a-fast-protein-binding-site-comparison-algorithm-for-proteome-wid/", "prompt": "Return the abstract verbatim, authors, DOI, method name, any runtime numbers."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:20

```
{"query": "ProCare computer vision approach align compare protein cavities point cloud registration Eguida Rognan", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:21

```
{"query": "SiteRadar binding site", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:21

```
{"query": "FLAPP fast local alignment protein pockets runtime comparisons per second", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:34:22

```
{"query": "OneProt multimodal protein foundation model pocket", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "FLAPP fast local alignment protein pockets runtime comparisons per second"

Links: [{"title":"Fast Local Alignment of Protein Pockets (FLAPP): A system-compiled program for large-scale binding site alignment","url":"https://www.biorxiv.org/content/10.1101/2022.07.13.499925.full.pdf"},{"title":"ALAE: Accelerating Local Alignment with Affine Gap Exactly in Biosequence Databases","url":"https://arxiv.org/pdf/1208.0274"},{"title":"CLeFAPS: Fast Flexible Alignment of Protein Structures Based on Conformational Letters","url":"https://arxiv.org/pdf/0903.0582"},{"title":"iisc.ac.in","url":"https://eprints.iisc.ac.in/77463"},{"title":"Fast Local Alignment of Protein Pockets (FLAPP): A System-Compiled Program for Large-Scale Binding Site Alignment","url":"https://repository.ias.ac.in/130386"},{"title":"api.openalex.org","url":"https://api.openalex.org/works/doi:10.1021%2FACS.JCIM.2C00967"},{"title":"Chandran Sakthivel=3AN=3A=3A","url":"https://eprints.iisc.ac.in/view/people/Chandran_Sakthivel=3AN=3A=3A.html"},{"title":"From: Accelerating large-scale protein structure alignments with graphics processing units","url":"https://bmcresnotes.biomedcentral.com/articles/10.1186/1756-0500-5-116/tables/2"},{"title":"FLAG: Fast Local Alignment Generating Methodology","url":"https://eprints.ugd.edu.mk/5706/"},{"title":"FLAG Fast Local Alignment Generating Methodology","url":"https://www.academia.edu/3070784/FLAG_Fast_Local_Alignment_Generating_Methodology"}]

The sea
… [1,586 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "SiteRadar binding site"

Links: [{"title":"Site2Vec: a reference frame invariant algorithm for vector embedding of protein-ligand binding sites","url":"https://arxiv.org/pdf/2003.08149"},{"title":"ProSiteHunter: A unified framework for sequence-based prediction of protein-nucleic acid and protein-protein binding sites","url":"https://www.biorxiv.org/content/10.1101/2025.10.22.683834.full.pdf"},{"title":"SiteHopper - a unique tool for binding site comparison","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3980140/"},{"title":"Mapping the 3D structures of small molecule binding sites","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5395517/"},{"title":"Binding site localization on non-homogeneous cell surfaces using topological image averaging","url":"https://www.biorxiv.org/content/10.1101/2020.11.03.366476.full.pdf"},{"title":"Site4Drug: Predicting Drug-Binding Target Sites with an AI Agent","url":"https://arxiv.org/pdf/2606.01816"},{"title":"Systems and methods for artificial intelligence-based binding site prediction and search space filtering for biological scaffold design","url":"https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12027235"},{"title":"Methods for identifying ligand binding sites in a biomolecule","url":"https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6730484"},{"title":"www.schrodinger.com","url":"https://www.schrodinger.com/platform/products/sitemap/"},{"title":"accelevents.com","url":
… [2,832 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "OneProt multimodal protein foundation model pocket"

Links: [{"title":"OneProt: Towards multi-modal protein foundation models via latent space alignment of sequence, structure, binding sites and text encoders","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12614600/"},{"title":"OneProt: Towards Multi-Modal Protein Foundation Models","url":"https://arxiv.org/pdf/2411.04863"},{"title":"OneProt: Towards Multi-Modal Protein Foundation Models","url":"https://arxiv.org/html/2411.04863v2"},{"title":"web3.arxiv.org","url":"https://web3.arxiv.org/pdf/2411.04863"},{"title":"huggingface.co","url":"https://huggingface.co/HelmholtzAI-FZJ/oneprot-4/blob/main/README.md"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2411.04863v3"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2411.04863v1"},{"title":"mcml.ai","url":"https://mcml.ai/publications/fus+25/"},{"title":"mcml.ai","url":"https://mcml.ai/publications/fus+24"},{"title":"oneprot towards multi modal protein","url":"https://sotaverified.org/papers/oneprot-towards-multi-modal-protein"}]

OneProt is a multimodal protein model that aligns sequence, structure, binding pocket, and text encoders. It was first posted to arXiv in November 2024 and later published in PLOS Computational Biology in November 2025.

- **What it does:** The model integrates protein sequence, structure, binding sites, and text annotations. It uses the ImageBind framework, which aligns the latent spaces of the encoders while 
… [1,370 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "ProCare computer vision approach align compare protein cavities point cloud registration Eguida Rognan"

Links: [{"title":"2020 eguida","url":"https://lab.drugdesign.unistra.fr/publications/2020_eguida/"},{"title":"github.com","url":"https://github.com/unixjunkie/procare"},{"title":"ProCare: cavity similarity searching and its applications to fragment-based drug design","url":"https://www.blopig.com/blog/?p=5829"},{"title":"www.blopig.com","url":"https://www.blopig.com/blog/wp-json/wp/v2/posts/5829"},{"title":"EGUIDA Kossiwa Ikafui Merveille 2022 ED222","url":"https://publication-theses.unistra.fr/public/theses_doctorat/2022/EGUIDA_Kossiwa_Ikafui_Merveille_2022_ED222.pdf"},{"title":"Point Cloud Registration","url":"https://lab.drugdesign.unistra.fr/tags/point-cloud-registration/"},{"title":"ecrin.app.unistra.fr","url":"https://ecrin.app.unistra.fr/search/notice/view/2022STRAF049/tef/xml"},{"title":"File:Master internship cavity alignment","url":"https://igg.icube.unistra.fr/en/index.php/File:Master_internship-cavity_alignment.pdf?page=1"},{"title":"m. eguida","url":"https://lab.drugdesign.unistra.fr/authors/m.-eguida/"},{"title":"Category Archives: Protein Structure","url":"https://blopig.com/blog/category/protein-structure/page/6"}]

The search turned up the 2020 J. Med. Chem. paper by Eguida and Rognan that introduces ProCare, along with the code repository and a related PhD thesis.

- **The method:** Pockets are represented by pharmacophore-a
… [1,359 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
I can't reproduce the full abstract verbatim, because my quotes from this source are limited to 125 characters. Here is a summary of its content:

**Authors:** Shiliang Li, Chaoqian Cai, Jiayu Gong, Xiaofeng Liu, and Honglin Li (corresponding author). Affiliations are East China University of Science and Technology and Jiangzhong Pharmaceutical Co., Ltd.

**Publication:** *Proteins: Structure, Function and Bioinformatics*, vol. 89, no. 11, pp. 1541–1556, November 2021.

**DOI:** 10.1002/prot.26176

**Method name:** PocketShape, a sequence order-independent algorithm for comparing protein ligand binding sites. It accounts for backbone geometry, side-chain orientation, and the physicochemical properties of pocket-lining residues.

**Key results reported:**
- Retrieved 99.3% of similar binding site pairs and rejected 100% of dissimilar pairs on a dataset of 1,538 binding site pairs.
- Classified 83 enzyme structures with diverse functions into 12 clusters, which the authors say closely matches the actual structural classification.
- Outperformed other methods in protein profiling based on experimental data.
- Predicted new potential applications for the SARS-CoV-2 drugs remdesivir and 11a.

**Runtime numbers:** The page does not report any specific runtime or timing figures. It only describes PocketShape as "time-efficient" without giving measurements.
```


**→ tool call `WebFetch`** · 2026-10-27 17:34:34

```
{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5845264/", "prompt": "Extract all reported computational runtimes / timings per pocket comparison for each tool evaluated (APoc, G-LoSA, SiteEngine, eMatchSite, ProBiS, PocketMatch, SMAP, IsoMIF, etc.), with exact numbers and the hardware. Also list which tools were evaluated and their headline performance (e.g. AUC/MCC on TOUGH-M1)."}
```


**← tool result**

```
**Runtimes: not reported.** The page text contains no per-comparison timings, wall-clock times, or hardware specifications. The only computing mention is an acknowledgement that Louisiana State University provided "computing resources," with no details. The page is also truncated partway through the reference list, so I can't rule out timing details in the omitted portion, but none appear in the visible text.

**Tools evaluated in the visible text:**

- **Direct pocket-alignment tools:** APoc, SiteEngine, G-LoSA
- **Indirect virtual-screening tools:** AutoDock Vina, rDock
- **Meta-predictors:** combinations of a direct tool with rDock or Vina (e.g., G-LoSA + rDock, SiteEngine + rDock)

eMatchSite and PocketMatch appear only in the reference list, and ProBiS, SMAP, and IsoMIF don't appear in the visible text. None of these were evaluated in the visible sections.

**Headline AUC results (from Table 1):**

| Tool | APoc dataset | TOUGH-M1 |
|---|---|---|
| APoc | 0.82 | 0.65 |
| SiteEngine | 0.60 | 0.66 |
| G-LoSA | 0.77 | 0.69 |
| Vina (indirect) | – | 0.55 |
| rDock (indirect) | – | 0.67 |
| APoc + rDock | – | 0.70 |
| SiteEngine + rDock | – | 0.76 |
| G-LoSA + rDock | – | 0.77 |

The paper does not give a headline MCC per tool. It reports MCC values only for individual example alignments (e.g., 0.74 and 0.71 for G-LoSA and APoc on one pair, 0.71 for G-LoSA on another, and 0.03 for APoc on a third).

[WebFetch note: this page's text is 130107 characters long and the answer abo
… [141 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:34:45

```
{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6224041/", "prompt": "Extract any reported runtimes/computation times for the binding site comparison tools evaluated (exact numbers, units, dataset, hardware). Also list all tools evaluated and which were best overall. Quote numbers precisely."}
```


**← tool result**

```
**Runtimes:** The visible content reports no exact runtimes, units, datasets, or hardware specifications. Computation time is discussed only qualitatively:

- Graph-based methods are described as enabling "a more accurate binding site characterization accompanied by higher run times." (Cavbase and Grim, versus the faster RAPMAD and TIFP.)
- Fingerprint- and histogram-based methods are said to be "usually characterized by low computational demands."
- For SMAP and SiteHopper, the authors note that "no additional computational costs arise" because they are insensitive to flexibility and need no structural ensembles.

The article text is truncated, so exact timings may appear in the omitted sections or supplementary material.

**Tools evaluated** (CMASA, COFACTOR, and PocketFEATURE were not analyzed):

- **Residue-based:** Cavbase, RAPMAD, FuzCav, PocketMatch, SiteAlign, SMAP, TM-align
- **Surface-based:** ProBiS, Shaper/VolSite/Shaper, SiteEngine, SiteHopper
- **Interaction-based:** IsoMIF, KRIPO, TIFP, Grim

**Best performers:** The article does not name one overall winner. It concludes that the choice depends on the application. Results by dataset include:

- **Identical sequences:** IsoMIF and KRIPO "clearly outperform Grim and TIFP," and residue- and surface-based tools are recommended for relationships between sites with different ligands.
- **NMR ensembles:** Residue- and surface-based tools performed poorly, while SMAP, TM-align, SiteAlign, SiteEngine, and ProBiS gave re
… [688 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:34:55

```
{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6224041/", "offset": 100000, "prompt": "Extract any reported runtimes/computation times per comparison for any tool (exact numbers, units, hardware). Quote precisely. Also any statements about which tools are fastest."}
```


**← tool result**

```
**Hardware:** "Intel Xeon workstation (E5-2690 with 2.90GHz and 32 GB RAM) in a serial manner (single core)," with run time measured via the Linux "time" command (user time).

**Average run time per comparison (Table 6, data set 5, 100 structures; units in seconds):**

| Tool | Avg. time per comparison (s) |
|---|---|
| PocketMatch | 0.000028 |
| KRIPO | 0.000092 |
| RAPMAD | 0.000285 |
| FuzCav | 0.000607 |
| FuzCav (PDB) | 0.000612 |
| TM-align | 0.006596 |
| Shaper (PDB) | 0.039542 |
| Shaper | 0.039845 |
| VolSite/Shaper | 0.043070 |
| ProBiS | 0.047932 |
| VolSite/Shaper (PDB) | 0.049942 |
| TIFP | 0.092913 |
| TIFP (PDB) | 0.093056 |
| Grim (PDB) | 0.186034 |
| Grim | 0.233240 |
| IsoMIF | 0.256144 |
| SiteHopper | 0.382861 |
| Cavbase | 2.635396 |
| SMAP | 4.234674 |
| SiteEngine | 8.119354 |
| SiteAlign | 28.632641 |

Some averages are based on fewer comparisons than the full 10,000 because of failed preparations. For example, Cavbase and RAPMAD used 8,281 comparisons.

**Statements about speed:**

- The authors group the tools into three tiers: "very fast methods (several microseconds per comparison), moderately fast methods (several milliseconds per comparison), and comparably slow methods (several seconds per comparison)."
- PocketMatch is the fastest in the table. For one site against the sc-PDB (9,283 entries) on a single CPU, "PocketMatch will perform these comparisons within 0.28 seconds."
- For the same task, SiteAlign would need "three days."
- "RAPMAD is app
… [477 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:35:17

```
{"command": "for r in BenevolentAI/DeeplyTough 3D-e-Chem/kripodb volkamerlab/kissim 3BioCompBio/pyScoMotif steineggerlab/folddisco vttresearch/ActSeek LPDI-EPFL/masif bowen-gao/DrugCLIP TravisWheelerLab/Simpatico tugceoruc/epocs unixjunkie/procare shiwentao00/Graphsite-classifier steineggerlab/foldseek soedinglab/MMseqs2 pharmai/plip insilab/probis janezkonc/probis LPDI-EPFL/masif_seed; do\ncurl -s https://api.github.com/repos/$r | python3 -c \"import sys,json;d=json.load(sys.stdin);print('$r', d.get('license',{}) and d['license'].get('spdx_id'), d.get('pushed_at'), d.get('stargazers_count'), d.get('message',''))\"; done", "description": "Check GitHub repos licence and last push date"}
```


**← tool result**

```
BenevolentAI/DeeplyTough NOASSERTION 2023-04-07T09:33:44Z 168 
3D-e-Chem/kripodb Apache-2.0 2021-01-20T14:05:29Z 8 
volkamerlab/kissim MIT 2023-09-24T14:41:45Z 34 
3BioCompBio/pyScoMotif None 2023-11-18T15:49:17Z 37 
steineggerlab/folddisco GPL-3.0 2026-10-15T03:46:17Z 221 
vttresearch/ActSeek NOASSERTION 2026-06-25T12:22:02Z 33 
LPDI-EPFL/masif Apache-2.0 2024-06-19T17:40:17Z 785 
bowen-gao/DrugCLIP NOASSERTION 2026-01-26T07:50:26Z 252 
TravisWheelerLab/Simpatico BSD-3-Clause 2026-09-26T17:54:03Z 3 
tugceoruc/epocs Apache-2.0 2025-08-11T09:54:48Z 18 
unixjunkie/procare NOASSERTION 2020-07-06T13:56:05Z 0 
shiwentao00/Graphsite-classifier MIT 2023-09-24T15:55:31Z 10 
steineggerlab/foldseek GPL-3.0 2026-09-09T09:30:49Z 1316 
soedinglab/MMseqs2 MIT 2026-10-27T11:03:59Z 2162 
pharmai/plip GPL-2.0 2026-07-03T15:05:08Z 725 
insilab/probis {} None None Not Found
janezkonc/probis {} None None Not Found
LPDI-EPFL/masif_seed Apache-2.0 2025-09-22T13:38:17Z 175
```


**→ tool call `Bash`** · 2026-10-27 17:35:28

```
{"command": "for q in \"probis\" \"IsoMif\" \"PocketMatch\" \"G-LoSA\" \"ProFSA\" \"LigUnity\" \"PocketVec\" \"FLAPP pocket\" \"ematchsite\" \"site2vec\" \"masif-neosurf\" \"BindCLIP\" \"PocketAnchor\" \"OneProt\" \"ErePOC\" \"PocketScope\" \"drugclip genome\" \"FuzCav\" \"pocket zernike\" \"APoc pocket\"; do\necho \"== $q\"; curl -s \"https://api.github.com/search/repositories?q=$(python3 -c \"import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))\" \"$q\")&per_page=4\" | python3 -c \"import sys,json;d=json.load(sys.stdin);[print(' ',i['full_name'],(i.get('license') or {}).get('spdx_id'),i['pushed_at'][:10],i['stargazers_count'],(i.get('description') or '')[:80]) for i in d.get('items',[])] if 'items' in d else print(d.get('message'))\"; sleep 7; done", "description": "Search GitHub for pocket method repositories", "timeout": 300000}
```


**← tool result**

```
== probis
  jonathankl4/HotelGo None 2022-12-16 0 Project Probis
  gracielo2804/Probis2 None 2021-06-16 0 Project Probis 2 
  doniebelva/kanvas-inovasi-probis None 2026-06-19 0 Kanvas inovasi probis
  XSmas29/Proyek_PROBIS None 2021-11-01 0 proyek probis aplikasi perpustakaan
== IsoMif
  mtthchrtr/IsoMif None 2016-05-07 5 IsoMif Development
== PocketMatch
  1337deepesh/PocketMatch_v2.0 None 2015-05-12 9 PocketMatch(version2.0): A parallel algorithm for the detection
  u3621195/pocketmatch None 2026-05-23 0 
  hoangthehung/pocketmatch None 2018-01-24 0 testing
  tuayang/pocketmatch None 2025-04-03 0 
== G-LoSA
  lanl/losalamos.github.com None 2016-01-11 5 Portal for LANL open source at GitHub
  ipendlet/protein-structure-alignment-glosa MIT 2026-10-02 0 G-LoSA alignment service
  rladies/losangeles_20170416_ggplot2 None 2017-04-18 2 R-Ladies LA - ggplot2 meetup
  AFTABSIDDIQUE/LOSApiGateway None 2025-08-31 0 
== ProFSA
  bowen-gao/ProFSA MIT 2024-06-03 23 [ICLR 2024] ProFSA: Self-supervised Pocket Pretraining via Protein Fragment-Surr
  THU-ATOM/ProFSA MIT 2024-08-29 14 
  PROFSANTARELLI/PROFSANTARELLI None 2025-10-16 16 Config files for my GitHub profile.
  Profsain/Profsain-Portfolio None 2023-04-24 3 A personal portfolio project to showcase my skills, projects, achievement and wa
== LigUnity
  IDEA-XL/LigUnity Apache-2.0 2026-03-30 63 Official implementation for LigUnity: Hierarchical affinity landscape navigation
  heneil/Dual_Ent_LigUnity Apache-2.0 2026-01-23 1 Hyperboli
… [3,192 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:38:08

```
{"command": "for p in pyscomotif kissim kripodb plip folddisco foldseek deeplytough actseek drugclip probis isomif pocketmatch unicore epocs oneprot simpatico ligunity; do printf \"%-12s pypi: \" $p; curl -s -o /dev/null -w \"%{http_code}\" https://pypi.org/pypi/$p/json; printf \"  bioconda: \"; curl -s -o /dev/null -w \"%{http_code}\" https://api.anaconda.org/package/bioconda/$p; printf \"  conda-forge: \"; curl -s -o /dev/null -w \"%{http_code}\\n\" https://api.anaconda.org/package/conda-forge/$p; done\nfor p in apoc probis tm-align mmseqs2; do printf \"%-10s bioconda \" $p; curl -s https://api.anaconda.org/package/bioconda/$p | python3 -c \"import sys,json;d=json.load(sys.stdin);print(d.get('latest_version'),d.get('license'))\"; done\ncurl -s https://pypi.org/pypi/pyscomotif/json | python3 -c \"import sys,json;d=json.load(sys.stdin)['info'];print(d['version'],d['license'])\"\ncurl -s https://api.anaconda.org/package/bioconda/folddisco | python3 -c \"import sys,json;d=json.load(sys.stdin);print('folddisco',d.get('latest_version'),d.get('license'))\"\ncurl -s https://api.anaconda.org/package/conda-forge/kissim | python3 -c \"import sys,json;d=json.load(sys.stdin);print('kissim',d.get('latest_version'),d.get('license'))\"", "description": "Check pip/conda availability of tools", "timeout": 200000}
```


**← tool result**

```
pyscomotif   pypi: 200  bioconda: 404  conda-forge: 404
kissim       pypi: 404  bioconda: 404  conda-forge: 200
kripodb      pypi: 404  bioconda: 404  conda-forge: 404
plip         pypi: 200  bioconda: 404  conda-forge: 200
folddisco    pypi: 404  bioconda: 200  conda-forge: 404
foldseek     pypi: 404  bioconda: 200  conda-forge: 404
deeplytough  pypi: 404  bioconda: 404  conda-forge: 404
actseek      pypi: 404  bioconda: 404  conda-forge: 404
drugclip     pypi: 200  bioconda: 404  conda-forge: 404
probis       pypi: 404  bioconda: 404  conda-forge: 404
isomif       pypi: 404  bioconda: 404  conda-forge: 404
pocketmatch  pypi: 200  bioconda: 404  conda-forge: 404
unicore      pypi: 404  bioconda: 200  conda-forge: 404
epocs        pypi: 404  bioconda: 404  conda-forge: 404
oneprot      pypi: 404  bioconda: 404  conda-forge: 404
simpatico    pypi: 404  bioconda: 404  conda-forge: 404
ligunity     pypi: 404  bioconda: 404  conda-forge: 404
apoc       bioconda 1b16 This software is freely available to ALL users.
probis     bioconda None None
tm-align   bioconda None None
mmseqs2    bioconda 17.b804f MIT
0.9.50 None
folddisco 2.9375a2d GPL-3.0-or-later
kissim 1.0.1 MIT
```


**→ tool call `Bash`** · 2026-10-27 17:38:26

```
{"command": "for p in drugclip pocketmatch kripodb; do curl -s https://pypi.org/pypi/$p/json | python3 -c \"import sys,json;d=json.load(sys.stdin)['info'];print('$p',d['version'],d['summary'],d['home_page'],d['project_urls'])\" 2>/dev/null || echo \"$p none\"; done\ncurl -s https://api.github.com/repos/3D-e-Chem/kripodb/readme | python3 -c \"import sys,json,base64;print(base64.b64decode(json.load(sys.stdin)['content']).decode()[:1500])\"", "description": "Inspect PyPI entries for drugclip, pocketmatch"}
```


**← tool result**

```
drugclip 0.1.2 Multimodal Graph-Text Contrastive Learning for Drug Design https://huggingface.co/homerquan/DrugClip {'Homepage': 'https://huggingface.co/homerquan/DrugClip'}
pocketmatch 1.2.0 pocketmatching https://github.com/louetadelie1/benchmark_phys.git/ {'Homepage': 'https://github.com/louetadelie1/benchmark_phys.git/'}
kripodb none
# Kripo DB

[![Build Status](https://travis-ci.org/3D-e-Chem/kripodb.svg?branch=master)](https://travis-ci.org/3D-e-Chem/kripodb)
[![Build status](https://ci.appveyor.com/api/projects/status/diign2fenvai0dst?svg=true)](https://ci.appveyor.com/project/3D-e-Chem/kripodb)
[![Codacy Grade Badge ](https://api.codacy.com/project/badge/Grade/4878758675a0402bb75019672fa6e45c)](https://www.codacy.com/app/3D-e-Chem/kripodb?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=3D-e-Chem/kripodb&amp;utm_campaign=Badge_Grade)
[![Codacy Coverage Badge](https://api.codacy.com/project/badge/Coverage/4878758675a0402bb75019672fa6e45c)](https://www.codacy.com/app/3D-e-Chem/kripodb?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=3D-e-Chem/kripodb&amp;utm_campaign=Badge_Coverage)
[![DOI](https://zenodo.org/badge/19641/3D-e-Chem/kripodb.svg)](https://zenodo.org/badge/latestdoi/19641/3D-e-Chem/kripodb)
[![Docker Hub](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/3dechem/kripodb/)
[![Documentation Status](https://readthedocs.org/projects/kripodb/badge/?version=latest)](http://kripodb.readthedocs.io/en/latest/?bad
… [340 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:38:31

```
{"url": "https://www.biorxiv.org/content/10.1101/2025.07.06.663357v1", "prompt": "Give the full abstract, authors, posting date, and any runtime/speed/index-size numbers (e.g. query time on AFDB50, comparisons with pyScoMotif, MASTER etc.). Also any journal publication link."}
```


**→ tool call `WebFetch`** · 2026-10-27 17:38:32

```
{"url": "https://github.com/steineggerlab/folddisco", "prompt": "Summarize: what Folddisco does, features indexed, input format (motif residues), speed numbers, prebuilt indices (AFDB50, PDB etc.), citation (journal + DOI), licence, install methods."}
```


**← tool result**

```
**Folddisco** is a tool for searching discontinuous structural motifs in protein structures. Its own description is "Fast indexing and search of discontinuous motifs in protein structures." It is aimed at large databases, covering thousands of proteomes or millions of structures.

**What it indexes and searches**
- It builds an index of precomputed geometric hashes from PDB/mmCIF files or Foldcomp databases.
- Hash types are `default`, `pdb`, `trrosetta`, `ppf`, and `3di`, with adjustable distance and angle bins.
- Queries can use distance (`-d`) and angle (`-a`) tolerances, plus sensitive and confident modes.
- Amino-acid substitution schemes (`blosum62`, `group`, `size`) and index-time query expansion are supported.
- Output can be per match or per structure, with sorting, filtering, and custom columns.

**Input format (motif residues)**
- Single query: `folddisco query -p query.pdb -q B57,B102,C195 -i index`. Omitting `-q` searches the whole structure.
- Residues use chain plus number (`B57`). Separators (`B_57`) and inclusive ranges (`1-10`) are allowed.
- Substitutions use `:ALT`, e.g. `164:H` or `247:ND`. Categories are `X` (any), `p` (positive), `n` (negative), `h` (polar), `b` (hydrophobic), `a` (aromatic), and `*` (substitution scheme).
- Batch mode takes a tab-separated file: structure path, motif residues, and an optional output path.

**Speed**
- The page gives no benchmark numbers. It only says the tool is designed for efficiency at large scale and that the webse
… [1,009 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
**Title:** Structural motif search across the protein-universe with Folddisco (bioRxiv preprint)

**Authors:** Hyunbin Kim, Rachel Seongeun Kim, Milot Mirdita, Martin Steinegger. Affiliations are Seoul National University, with Steinegger listed as corresponding author.

**Posted:** July 06, 2025. DOI: 10.1101/2025.07.06.663357

**Abstract (paraphrased):** Finding similar structural motifs, which are short, functionally important 3D patterns, across large structure collections is computationally prohibitive. Folddisco addresses this with an index of position-independent geometric features, including side-chain orientation, and a rarity-based scoring system. It indexes 53 million AFDB50 structures into 1.45 TB within 24 hours and supports discontinuous and segment motifs. The authors report it is more accurate and storage-efficient than state-of-the-art methods and "an order of magnitude faster." Software is free, with a webserver available.

**Speed and index-size numbers:**
- Indexing: 53 million AFDB50 structures into 1.45 TB within 24 hours
- Speed: described as "an order of magnitude faster" than state-of-the-art methods, with no specific query times given
- Comparisons with pyScoMotif or MASTER: not mentioned in the page content

**Availability:** folddisco.foldseek.com (software), search.foldseek.com/folddisco (webserver), and github.com/steineggerlab/folddisco-analysis (analysis code)

**Journal publication:** None listed. The page only shows the bioRxiv preprint.

**C
… [76 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:38:46

```
{"query": "MetalS3 metal site similarity search tool Valasatava Rosato Andreini Bioinformatics", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:38:47

```
{"query": "metal binding site structural alignment iterative closest point metalloprotein AlphaFold 2024 2025", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:38:48

```
{"query": "ActSeek Castillo Ollila runtime AlphaFold proteins per second", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:38:48

```
{"query": "ProBiS-Fold AlphaFold human structures annotation ligands Konc 2022 JCIM", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "MetalS3 metal site similarity search tool Valasatava Rosato Andreini Bioinformatics"

Links: [{"title":"flore.unifi.it","url":"https://flore.unifi.it/handle/2158/958362"},{"title":"metalweb.cerm.unifi.it","url":"https://metalweb.cerm.unifi.it/tools/metals3/"},{"title":"nih.gov","url":"https://pubmed.ncbi.nlm.nih.gov/24699831"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC4377587"},{"title":"flore.unifi.it","url":"https://flore.unifi.it/handle/2158/1008036"},{"title":"thesis final","url":"https://flore.unifi.it/retrieve/e398c378-f0d7-179a-e053-3705fe0a4cff/thesis_final.pdf"},{"title":"metalweb.cerm.unifi.it","url":"https://metalweb.cerm.unifi.it/tools/metals2/"},{"title":"VALASATAVA, YANA","url":"https://flore.unifi.it/cris/rp/rp03801"},{"title":"VALASATAVA, YANA","url":"https://flore.unifi.it/cris/rp/rp03801?type=all"},{"title":"Minimal Functional Sites in Metalloproteins and Their Usage in Structural Bioinformatics","url":"https://0-www-mdpi-com.brum.beds.ac.uk/1422-0067/17/5/671"}]

MetalS3 is a database-mining tool, published in 2014 in the *Journal of Biological Inorganic Chemistry* by Yana Valasatava, Antonio Rosato, Gabriele Cavallaro, and Claudia Andreini (PubMed ID 24699831).

- **Purpose:** It searches the MetalPDB database for metal sites that resemble a query site. It was built to identify metal sites with structural similarity to a query metal site within MetalPDB's minimal functional sites (MFSs) i
… [881 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "ActSeek Castillo Ollila runtime AlphaFold proteins per second"

Links: [{"title":"AF_Cache: Efficient Pipeline for Running AlphaFold for High-Throughput Protein-Protein Interaction Prediction","url":"https://arxiv.org/pdf/2606.04566"},{"title":"ParaFold: Paralleling AlphaFold for Large-Scale Predictions","url":"https://arxiv.org/pdf/2111.06340"},{"title":"# Breaking the MSA Storage Bottleneck to Accelerate AlphaFold","url":"https://www.weka.io/blog/ai-ml/breaking-the-msa-storage-bottleneck-to-accelerate-alphafold/"},{"title":"www.emergentmind.com","url":"https://www.emergentmind.com/papers/2606.04566"},{"title":"ParaFold: Paralleling AlphaFold for Large-Scale Predictions","url":"https://ar5iv.labs.arxiv.org/html/2111.06340"},{"title":"huggingface.co","url":"https://huggingface.co/papers/2111.06340"},{"title":"par.nsf.gov","url":"https://par.nsf.gov/servlets/purl/10358833"},{"title":"web3.arxiv.org","url":"https://web3.arxiv.org/pdf/2111.06340"},{"title":"Quantitative Biology > Biomolecules","url":"https://web3.arxiv.org/abs/2111.06340"},{"title":"cfp.openondemand.org","url":"https://cfp.openondemand.org/2025/talk/NYHCQF/"}]

I couldn't find anything on "ActSeek" or the Castillo/Ollila runtime work in these results, so I can't confirm a proteins-per-second figure from them.

The closest material is about AlphaFold throughput generally:

- **ParaFold** (arXiv 2111.06340) reports running model 1 inference on about 20,000 small proteins in five hour
… [736 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "metal binding site structural alignment iterative closest point metalloprotein AlphaFold 2024 2025"

Links: [{"title":"Benchmarking Zinc-Binding Site Predictors: A Comparative Analysis of Structure-Based Approaches","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12117554/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC8785651"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC12117554"},{"title":"Metal3D: Accurate prediction of transition metal ion location via deep learning","url":"https://neurips.cc/virtual/2022/61217"},{"title":"Metal3D: Accurate prediction of transition metal ion location via deep learning","url":"https://neurips.cc/virtual/2022/59059"},{"title":"nips.cc","url":"https://nips.cc/virtual/2022/59059"},{"title":"supermetal a generative ai framework for rapid and precise metal","url":"https://researchportal.hw.ac.uk/en/publications/supermetal-a-generative-ai-framework-for-rapid-and-precise-metal-/"},{"title":"Journal article","url":"https://iro.uiowa.edu/esploro/outputs/journalArticle/Identification-of-Iron-Sulfur-Fe-S-Cluster-and/9984288722002771"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2021.10.08.463726v1.full.pdf+html"},{"title":"PhD BAZAYEVA","url":"https://flore.unifi.it/retrieve/c2673cb5-6847-41b6-89ce-0c673984ef90/PhD_BAZAYEVA.pdf"}]

The search didn't turn up any work that uses iterative closest point (ICP) for metal-
… [1,808 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "ProBiS-Fold AlphaFold human structures annotation ligands Konc 2022 JCIM"

Links: [{"title":"Database Commons","url":"https://ngdc.cncb.ac.cn/databasecommons/database/id/8322"},{"title":"cris.cobiss.net","url":"https://cris.cobiss.net/ecris/si/en/project/20019"},{"title":"Guest lecture by Dusanka Janezic","url":"https://moltag.univie.ac.at/archive/details/news/guest-lecture-by-dusanka-janezic"},{"title":"Central Technological Library of the University of Ljubljana (CTK)","url":"https://plus.cobiss.net/cobiss/si/en/bib/ctk/126704899"},{"title":"中文 | English","url":"https://pharmacy.ecust.edu.cn/_t341/2023/1107/c2590a162380/page.htm"},{"title":"中文 | English","url":"https://pharmacy.ecust.edu.cn/2023/1107/c2590a162380/page.htm"},{"title":"pharmacy.ecust.edu.cn","url":"https://pharmacy.ecust.edu.cn/_t114/2023/1107/c2590a162380/page.htm"},{"title":"ProBiS-Fold approach for binding site detection for whole structural human proteome in drug discovery","url":"https://famnit.upr.si/en/research/programmes-projects/J1-4414-EN"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2022.01.25.477691v1.full.pdf"},{"title":"probis fold approach for binding site detection for whole structural human proteome in drug discovery","url":"https://www.ffa.uni-lj.si/en/research/projects/arrs/probis-fold-approach-for-binding-site-detection-for-whole-structural-human-proteome-in-drug-discovery"}]

The search turned up the 2022 paper and several descr
… [1,984 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:39:00

```
{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12343037/", "prompt": "Describe ActSeek's algorithm (representation, alignment e.g. ICP/KD-tree/RANSAC, scoring), runtime numbers (per protein, total for AFDB/ Swiss-Prot / proteomes, hardware), datasets searched, licence/code, DOI and journal."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:39:00

```
{"query": "\"Master of Metals\" zinc sites AlphaFold models templates proteome", "mode": "standard"}
```


**← tool result**

```
The page you provided is a browser verification (reCAPTCHA) interstitial from pmc.ncbi.nlm.nih.gov. It contains no article text, so I can't describe ActSeek's algorithm, runtimes, datasets, licence, DOI, or journal from it.

To get an answer, you could:
- Open the PMC article directly once the check completes, then paste its text or relevant sections here.
- Paste the abstract, methods, and availability sections, which typically cover the algorithm, datasets, hardware, and code licence.
```


**← tool result**

```
Web search results for query: ""Master of Metals" zinc sites AlphaFold models templates proteome"

Links: [{"title":"Hunting down zinc(II)-binding sites in proteins with distance matrices","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10630175/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10630175"},{"title":"academic.oup.com","url":"https://academic.oup.com/bioinformatics/article/39/11/btad653/7333116"},{"title":"BriefingsBioinfo MoM2 2026","url":"https://flore.unifi.it/retrieve/7b0db234-c4a3-48af-a42b-18e570704aa4/BriefingsBioinfo_MoM2_2026.pdf"},{"title":"PhD BAZAYEVA","url":"https://flore.unifi.it/retrieve/c2673cb5-6847-41b6-89ce-0c673984ef90/PhD_BAZAYEVA.pdf"},{"title":"flore.unifi.it","url":"https://flore.unifi.it/handle/2158/1352495"},{"title":"mechtinger et al 25","url":"https://www.cs.haifa.ac.il/~trachel/pdfs/mechtinger_et_al_25.pdf"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC12117554"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC8785651"},{"title":"Machine Learning to predict zinc metal ion binding sites in proteins: Master of Metals2","url":"https://aria-booking.leeds.ac.uk/scientifichighlights/machine-learning-to-predict-zinc-metal-ion-binding-sites-in-proteins-master-of-metals2"}]

Master of Metals (MoM) is a zinc-site predictor built for AlphaFold-style structural models, and it has a second-generation successor.

- **Original MoM (2023):** It us
… [1,285 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:39:10

```
{"url": "https://www.biorxiv.org/content/10.1101/2025.02.11.637678v1.full", "prompt": "Describe ActSeek's algorithm (representation, alignment e.g. ICP/KD-tree/RANSAC, scoring), runtime numbers (per protein, total for AFDB / proteomes, hardware), datasets searched, code licence."}
```


**→ tool call `WebFetch`** · 2026-10-27 17:39:11

```
{"url": "https://github.com/vttresearch/ActSeek", "prompt": "Describe the algorithm, runtime/speed claims, licence terms, install method (pip?), citation."}
```


**← tool result**

```
**Algorithm:** ActSeek searches AlphaFold database structures for proteins that have the same, or similar, amino acids in the same spatial positions as a seed structure. It uses the coordinates of at least three user-selected residues from the seed. Tunable settings include:
- distance thresholds for the average distance of mapped residues and for candidate hits
- a window of neighboring residues used to decide which region is the active site
- a maximum distance for other matched residues
- an iteration limit
- residue grouping, so chosen amino acids can be treated as interchangeable
- optional KVFinder comparison of the cavity around the active site with the seed's cavity

A test mode superimposes one chosen protein onto the seed and outputs the residue mapping and a PDB file.

**Runtime/speed claims:** The only speed claim is in the publication title, which calls the method a "fast and accurate search algorithm." The page gives no benchmarks, timings, or hardware details.

**Licence:** The repository has a LICENSE file, but the captured page does not show the license name or text. The LICENSE file itself would need to be checked.

**Installation:** Requires Python 3.6 or higher and pip. The page gives these steps:
- `pip install numpy biopython tqdm wget requests`
- `pip install cython`
- `pip install scipy`
- `pip install pyKVFinder`
- `pip install .` (run from the cloned repository)

The page does not indicate the package is published on PyPI. To test the install, run `c
… [365 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
**Representation:** ActSeek uses only the Cα and Cβ coordinates of selected residues. The user defines three main residues (e.g., catalytic or binding), optional additional residues, and neighboring residues in sequence (four by default).

**Pre-screening:** Before the costly 3D comparison, ActSeek checks that a query contains the three main residues with inter-residue distances within 3 Å of the seed. If more than 2,000 residue mappings are possible, a random subset is tested.

**Alignment:** The optimal rotation and translation are computed with singular value decomposition (SVD) and least-squares fitting, citing Arun et al. (1987) and Golub and Van Loan. The page does not mention ICP, KD-trees, or RANSAC.

**Scoring:**
- Average distances between mapped residues (main, additional, and neighboring) after superposition. Neighbor distances are used regardless of residue type.
- The average is divided by the number of residues averaged, which penalizes missing additional residues.
- The lowest-scoring mapping per structure is kept, and the structure is reported if that score is below a user-set threshold (default 1 Å).
- Supplementary measures include a structural mapping percentage (Cα pairs within 2 Å, via dynamic programming), a local alignment score, and an optional cavity comparison using pyKVFinder.

**Runtime:** A 24-CPU cluster node processes about 10,000 proteins in 2–10 minutes, depending on the number of possible mappings. The page gives no total runtime for the ful
… [886 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:39:27

```
{"url": "https://www.biorxiv.org/content/10.1101/2024.09.02.610777v1.full", "prompt": "Extract: pocket detection method used for AlphaFold structures, number of pockets/proteins, embedding dimension, speed numbers (e.g. pairs per day, compounds per second, total screen time and hardware), and any use of pocket-pocket similarity via DrugCLIP pocket embeddings. Also the database name and URL (GenomeScreenDB?) and code URL."}
```


**→ tool call `WebFetch`** · 2026-10-27 17:39:28

```
{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12259003/", "prompt": "Simpatico: summarize representation, comparison, runtime numbers, code licence, and whether pocket-pocket similarity was evaluated (e.g., ProSPECCTs/TOUGH-M1)."}
```


**← tool result**

```
The content you provided is a browser verification page (reCAPTCHA) for pmc.ncbi.nlm.nih.gov, not the Simpatico article. It contains nothing about representation, comparison methods, runtime, code licensing, or pocket-pocket similarity evaluation, so I can't summarize those points from it.

To get the summary, you could:
- Paste the article's text (abstract, methods, results, and code availability sections), or
- Open the article directly once the browser check clears, then share the relevant sections.
```


**← tool result**

```
**Pocket detection for AlphaFold structures**
- Fpocket detects initial pockets. The GenPack step then removes side chains, uses a generative model conditioned on the backbone, and repacks side chains with physics-based refinement.
- Homology alignment is also used. The page does not name the alignment tool for this step, though TM-align is cited earlier for structure alignment.

**Number of pockets/proteins**
- More than 20,000 pockets from about 10,000 human proteins.
- The database spans 9,908 targets.
- The screen yielded over 2 million potential hit molecules.

**Embedding dimension**
- Not stated in the page.

**Speed and hardware**
- Over 500 million drug-like molecules from ZINC and Enamine REAL were screened.
- The screen involved more than 10 trillion scoring operations on protein-ligand pairs, completed in about 24 hours on a single node with 8 A100 GPUs.
- This works out to roughly 10 trillion pairs per day, or about 1.2 × 10⁸ pairs per second (my calculation, not a figure from the page).
- Compounds per second are not reported.
- On LIT-PCBA, screening took 38 seconds with pre-encoding, versus 3 days for Glide, 22 hours for Uni-Dock, and 3 hours for PLANET.

**Pocket-pocket similarity via DrugCLIP pocket embeddings**
- Not used for the genome-wide screen. The page mentions pocket matching only as a downstream evaluation of the pretrained pocket encoder (Supplementary Table 1).

**Database name and URL**
- The name "GenomeScreenDB" does not appear. The page refers
… [438 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:39:43

```
{"query": "MaSIF-search fingerprint descriptors runtime seconds compared to docking ZDOCK patches Gainza 2020", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:39:44

```
{"query": "PocketVec inverse virtual screening pocket descriptors Nature Communications 2024 Balestra Mestres Aloy", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:39:44

```
{"query": "ultrafast shape recognition USR applied to protein binding pockets similarity", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:39:45

```
{"query": "Chikhi Sael Kihara real-time pocket database search 3D Zernike descriptors seconds Pocket-Surfer", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "PocketVec inverse virtual screening pocket descriptors Nature Communications 2024 Balestra Mestres Aloy"

Links: [{"title":"Comprehensive detection and characterization of human druggable pockets through novel binding site descriptors","url":"https://www.biorxiv.org/content/10.1101/2024.03.14.584971.full.pdf"},{"title":"Nature Communications (Sep 2024)","url":"https://doaj.org/article/8c11db43ff354f759520de8c28ea0279"},{"title":"memoir.icrea.cat","url":"https://memoir.icrea.cat/?p=5848"},{"title":"Characterization of druggable pockets in the human proteome","url":"https://www.icrea.cat/impact/outreach/scientific-highlights/910/characterization-of-druggable-pockets-in-the-human-proteome/"},{"title":"Characterization of druggable pockets in the human proteome","url":"https://www.icrea.cat/es/impacto/outreach/resultados-destacados/910/characterization-of-druggable-pockets-in-the-human-proteome"},{"title":"Characterization of druggable pockets in the human proteome","url":"https://www.icrea.cat/ca/impacte/divulgacio/resultats-destacats/910/characterization-of-druggable-pockets-in-the-human-proteome"},{"title":"IDEAS home Printed from https://ideas.repec.org/a/nat/natcom/v15y2024i1d10.1038_s41467-024-52146-3.html","url":"https://ideas.repec.org/a/nat/natcom/v15y2024i1d10.1038_s41467-024-52146-3.html"},{"title":"Raül Andero Galí","url":"https://memoir.icrea.cat/?p=5860"},{"title":"Raül Andero Galí","url":"https://memoir.icrea.cat/2024/scientific-highl
… [1,735 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "ultrafast shape recognition USR applied to protein binding pockets similarity"

Links: [{"title":"A new method for rapid comparison of protein binding pockets by capturing spatial distributions","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3980086/"},{"title":"PocketPicker: analysis of ligand binding-sites with shape descriptors","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1994066/"},{"title":"www.hkhlr.de","url":"https://www.hkhlr.de/node-export/pdf/299"},{"title":"Improvement of Methods for the Comparison of Protein Binding Sites","url":"https://www.hkhlr.de/en/node/299"},{"title":"Improvement of Methods for the Comparison of Protein Binding Sites","url":"https://www.hkhlr.de/de/node/299"},{"title":"PoSSuM: a database of known and potential ligand-binding sites in proteins","url":"https://cbrc3.cbrc.pj.aist.go.jp/~tomii/research/research.html"},{"title":"- Poster presentation","url":"https://jcheminf.biomedcentral.com/articles/10.1186/1758-2946-6-S1-P45"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/track/pdf/10.1186/1471-2105-11-47"},{"title":"A fast protein binding site comparison algorithm for proteome-wide protein function prediction and drug repurposing","url":"https://pure.ecnu.edu.cn/en/publications/a-fast-protein-binding-site-comparison-algorithm-for-proteome-wid/"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/313615"}]

The search didn't turn up a paper that 
… [1,675 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "MaSIF-search fingerprint descriptors runtime seconds compared to docking ZDOCK patches Gainza 2020"

Links: [{"title":"A novel interaction fingerprint derived from per atom score contributions: exhaustive evaluation of interaction fingerprint performance in docking based virtual screening","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5856854/"},{"title":"Re-Docking Scheme for Generating Near-Native Protein Complexes by Assembling Residue Interaction Fingerprints","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3712918/"},{"title":"Protein-protein docking using region-based 3D Zernike descriptors","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2800122/"},{"title":"Accelerating Protein Docking in ZDOCK Using an Advanced 3D Convolution Library","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3176283/"},{"title":"IDEAS home Printed from https://ideas.repec.org/a/plo/pone00/0069365.html","url":"https://ideas.repec.org/a/plo/pone00/0069365.html"},{"title":"Optimizing fragment and scaffold docking by use of molecular interaction fingerprints","url":"https://hal.archives-ouvertes.fr/hal-00195175"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/track/pdf/10.1186/1471-2105-10-407"},{"title":"docs.lib.purdue.edu","url":"https://docs.lib.purdue.edu/bioscipubs/75"},{"title":"Name | Running time [hr] | Speedup from ZDOCK 3.0 |","url":"https://scfbm.biomedcentral.com/articles/10.1186/1751-0
… [1,309 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "Chikhi Sael Kihara real-time pocket database search 3D Zernike descriptors seconds Pocket-Surfer"

Links: [{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3294165"},{"title":"Sample records for localization ligand binding","url":"https://www.science.gov/topicpages/l/localization+ligand+binding"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3009464"},{"title":"NAIST 奈良先端科学技術大学院大学 バイオサイエンス領域","url":"https://bsw3-2024.naist.jp/seminar/index.php?id=94"},{"title":"NAIST 奈良先端科学技術大学院大学 バイオサイエンス領域","url":"https://bsw3.naist.jp/seminar/index.php?id=94"},{"title":"3D-SURFER 2.0: web platform for real-time search and characterization of protein surfaces","url":"https://pubmed.ncbi.nlm.nih.gov/24573477/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2912717"},{"title":"back to program","url":"https://www.bic.kyoto-u.ac.jp/pathway/bic10years/abst/kihara.html"},{"title":"cbe.snu.ac.kr","url":"https://cbe.snu.ac.kr/%ea%b3%b5%ed%86%b5-%ea%b3%b5%ec%a7%80/document/6609"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC4341070"}]

The Chikhi, Sael, and Kihara paper is "Real-Time Ligand Binding Pocket Database Search Using Local Surface Descriptors" (PMID 20455259). It describes two pocket representations, one based on 2D pseudo-Zernike moments and one based on 3D Zernike descriptors, and both allow fast searches against a pocket dat
… [1,113 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:40:10

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\ncat > q3.txt <<'EOF'\nG-LoSA an efficient computational tool for local structure-centric biological studies and drug design Lee Im\nLarge-scale mining for similar protein binding pockets with RAPMAD retrieval on the fly becomes real Krotzky\nPocketAlign Yeturu Chandra binding site alignment\nPSIM protein binding site similarity\nFast Local Alignment of Protein Pockets FLAPP system-compiled program\nProCare computer vision approach to align and compare protein cavities fragment-based drug design\nPOEM pocket oriented elaboration of molecules subpocket similarity hit identification challenging targets\nSiteContext web server protein binding site comparison\nRetrieval of binding sites across AlphaFold human proteome protein language model representations\nLearning structure-based pocket representations for protein-ligand interaction prediction PocketAnchor\nHierarchical affinity landscape navigation through learning a shared pocket-ligand space\nSimpatico accurate ultra-fast virtual drug screening atomic embeddings\nOneProt towards multi-modal protein foundation models latent space alignment sequence structure binding sites text\nFoldseek fast and accurate protein structure search van Kempen\nMMseqs2 enables sensitive protein sequence searching for the analysis of massive data sets\npyScoMotif discovery of similar 3D structural motifs across protein
… [1,179 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
G-LoSA an efficient computational tool f | 10.1002/pro.2890 | G‐LoSA: An efficient computational tool for local structure‐centric biological studies and | Protein Science | 2016 | Lee
G-LoSA an efficient computational tool f | 10.1016/j.bpj.2014.11.2584 | G-Losa: An Efficient Computational Tool for Local Structure-Centric Biological Studies | Biophysical Journal | 2015 | Lee
Large-scale mining for similar protein b | 10.1021/ci5005898 | Large-Scale Mining for Similar Protein Binding Pockets: With RAPMAD Retrieval on the Fly B | Journal of Chemical Information and Mode | 2014 | Krotzky
Large-scale mining for similar protein b | 10.1093/bioinformatics/btt024 | APoc: large-scale identification of similar protein pockets | Bioinformatics | 2013 | Gao
PocketAlign Yeturu Chandra binding site  | 10.1021/ci200132z | PocketAlign A Novel Algorithm for Aligning Binding Sites in Protein Structures | Journal of Chemical Information and Mode | 2011 | Yeturu
PocketAlign Yeturu Chandra binding site  | 10.1101/2022.07.13.499925 | Fast Local Alignment of Protein Pockets (FLAPP): A system-compiled program for large-scale |  | 2022 | Sankar
PSIM protein binding site similarity     | 10.1007/s10930-013-9494-1 | Ligand Binding Site Similarity Identification Based on Chemical and Geometric Similarity | The Protein Journal | 2013 | Tu
PSIM protein binding site similarity     | 10.1002/prot.25293 | Resolving protein structure‐function‐binding site relationships from a binding site simila | Proteins: 
… [8,799 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:41:41

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\ncat > q4.txt <<'EOF'\nPharmacophore fingerprint-based approach to binding site subpocket similarity and its application to bioisostere replacement\nDe novo design of protein interactions with learned surface fingerprints Gainza\nTargeting protein-ligand neosurfaces with a generalizable deep learning tool Marchand\nProtein-protein interfaces recognition of similar spatial and chemical organizations Shulman-Peleg WABI\nPocketAnchor learning structure-based pocket representations Li Tian Zeng Cell Systems\nErePOC contrastive pocket representation ligand similarity DEL Nature Communications\nA robust and efficient algorithm for the shape description of protein structures and its application in predicting ligand binding sites Xie Bourne\nSelf-supervised pocket pretraining via protein fragment-surroundings alignment\n3D Zernike descriptors protein surface pocket comparison Kihara review\nPersistent homology binding site comparison topological fingerprint\nDrugCLIP pocket encoder Uni-Mol pocket pretraining Uni-Mol universal 3D molecular representation learning framework\nLigySIS binding site ligand site analysis Utgés Barton\nGenomeScreenDB\nEOF\npython3 cr.py < q4.txt", "description": "Fourth batch of Crossref lookups", "timeout": 300000}
```


**← tool result**

```
Pharmacophore fingerprint-based approach | 10.1021/ci3000776 | Pharmacophore Fingerprint-Based Approach to Binding Site Subpocket Similarity and Its Appl | Journal of Chemical Information and Mode | 2012 | Wood
Pharmacophore fingerprint-based approach | 10.1021/acs.jcim.4c00601.s001 | Subpocket Similarity-Based Hit Identification for Challenging Targets: Application to the  |  | None | ?
De novo design of protein interactions w | 10.1101/2022.06.16.496402 | <i>De novo</i>
                  design of site-specific protein interactions with learned |  | 2022 | Gainza
De novo design of protein interactions w | 10.1038/s41586-023-05993-x | De novo design of protein interactions with learned surface fingerprints | Nature | 2023 | Gainza
Targeting protein-ligand neosurfaces wit | 10.1101/2024.03.25.585721 | Targeting protein-ligand neosurfaces using a generalizable deep learning approach |  | 2024 | Marchand
Targeting protein-ligand neosurfaces wit | 10.1038/s41586-024-08435-4 | Targeting protein–ligand neosurfaces with a generalizable deep learning tool | Nature | 2025 | Marchand
Protein-protein interfaces recognition o | 10.1007/978-3-540-30219-3_17 | Protein-Protein Interfaces: Recognition of Similar Spatial and Chemical Organizations | Lecture Notes in Computer Science | 2004 | Shulman-Peleg
Protein-protein interfaces recognition o | 10.1002/prot.20580 | Generation and analysis of a protein–protein interface data set with similar chemical and  | Proteins: Structure, Function, a
… [2,966 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:42:17

```
{"url": "https://www.biorxiv.org/content/10.1101/2025.07.06.663357v1.full", "prompt": "Extract concrete runtime numbers: query time per motif on AFDB50/AFDB proteomes/PDB, number of threads/hardware, comparisons with pyScoMotif, MASTER, PDB Motif search (speed and AUC), index size and build time. Also describe the geometric feature (hash) definition. Quote numbers precisely."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:42:18

```
{"query": "dMaSIF fast end-to-end learning protein surfaces faster less memory than MaSIF runtime", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:42:18

```
{"query": "APoc pocket alignment Gao Skolnick 2013 runtime seconds per comparison PS-score", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "APoc pocket alignment Gao Skolnick 2013 runtime seconds per comparison PS-score"

Links: [{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3582269"},{"title":"Center for the Study of Systems Biology","url":"https://sites.gatech.edu/cssb/apoc"},{"title":"nih.gov","url":"https://pubmed.ncbi.nlm.nih.gov/23335017"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/5"},{"title":"PPS search","url":"https://zhanggroup.org/PPS-search/"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/6"},{"title":"biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/7"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/3"},{"title":"bmcbioinformatics.biomedcentral.com","url":"https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-018-2109-2/figures/9"},{"title":"Mercurial > repos > earlhaminst > apoc","url":"https://toolshed.g2.bx.psu.edu/repos/earlhaminst/apoc/comparison/67d2a6f3b4e3/apoc.xml?revcount=6"}]

The search found the APoc paper and its PS-score definition, but nothing on runtime per comparison in seconds.

- **The paper:** Mu Gao and Jeffrey Skolnick's APoc paper appeared in Bioinformat
… [1,198 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "dMaSIF fast end-to-end learning protein surfaces faster less memory than MaSIF runtime"

Links: [{"title":"Fast end-to-end learning on protein surfaces","url":"https://www.biorxiv.org/content/10.1101/2020.12.28.424589.full.pdf"},{"title":"A Survey of Deep Learning Methods in Protein Bioinformatics and its Impact on Protein Design","url":"https://arxiv.org/pdf/2501.01477"},{"title":"Sverrisson Fast End to End Learning on Protein Surfaces CVPR 2021 paper","url":"https://openaccess.thecvf.com/content/CVPR2021/papers/Sverrisson_Fast_End-to-End_Learning_on_Protein_Surfaces_CVPR_2021_paper.pdf"},{"title":"github.com","url":"https://github.com/rdk/dMaSIF"},{"title":"github.com","url":"https://github.com/FreyrS/dMaSIF"},{"title":"CSC2547 W21 3DDL dMaSIF Youheng Ge","url":"https://www.pair.toronto.edu/csc2547-w21/assets/slides/CSC2547-W21-3DDL-dMaSIF-Youheng Ge.pdf"},{"title":"Machine learning approaches for the study of protein surfaces","url":"https://www.epfl.ch/labs/lpdi/?p=227"},{"title":"Machine learning approaches for the study of protein surfaces","url":"https://www.epfl.ch/labs/lpdi/machine-learning-approaches-for-the-study-of-protein-surfaces/"},{"title":"MaSIF paper SS2025","url":"https://www-cbi.cs.uni-saarland.de/wp-content/uploads/2025/03/MaSIF-paper_SS2025.pdf"},{"title":"magazine.sciencepod.net","url":"https://magazine.sciencepod.net/?p=721132"}]

The search found consistent evidence that dMaSIF is much faster and lighter on memory than M
… [1,196 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
**Runtime and resource figures**

*Indexing*
- **AFDB50 (53M structures):** indexed in under 24 hours, producing about 1.45 TB. Hardware: four Intel Xeon Gold 6328HL CPUs, 6 TB RAM, 15.3 TB NVMe.
- **540K-structure database:** Folddisco took 26.5 minutes on 64 cores, versus 4.87 hours for pyScoMotif. Index size was 31.5 GB versus 79 GB.
- **AFDB50 extrapolated for pyScoMotif:** about 7.8 TB, or 5.38× Folddisco's size. The paper does not state a pyScoMotif time for AFDB50.
- **PDB (from the Introduction):** RCSB took 3.5 days and 55 GB for 160,467 structures. pyScoMotif took 20.5 hours and 73 GB for 195,000 structures.
- **Fig. 1g summary:** Folddisco indexes 18× faster than pyScoMotif and its index is 3.5× smaller.

*Querying*
- **Pre-filter on AFDB50:** about 13 seconds.
- **Pre-filter vs. pyScoMotif:** described as 50× faster. Fig. 1g reports up to 48× for the pre-filter.
- **Full pipeline vs. pyScoMotif (zinc finger):** about 3× shorter for all databases.
- **Single-database benchmark:** Folddisco's query time was more than 7× faster than any other method (12 threads).
- **Webserver:** a full zinc finger query across all databases takes about 100 seconds on a single core.
- **Pre-filter vs. full pipeline (SCOPe benchmark):** the pre-filter is about 15× faster.

*Hardware and measurement*
- Benchmarks ran on two 64-core AMD EPYC 7742 CPUs, 2 TB RAM, and 15.3 TB NVMe, except AFDB50 indexing (see above).
- Memory and elapsed time were measured with GNU `time -v`.

*AUC (area 
… [1,217 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:42:37

```
{"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3582269", "prompt": "Quote any runtime / CPU time / speed numbers for APoc or for SiteEngine comparisons. Also the algorithm (alignment approach: iterative dynamic programming + integer programming?)."}
```


**→ tool call `WebFetch`** · 2026-10-27 17:42:38

```
{"url": "https://www.biorxiv.org/content/10.1101/600304v2.full", "prompt": "DeeplyTough: Quote any runtime numbers (descriptor computation time, comparison time, comparisons per second, hardware). Also describe representation (voxel grid channels, size), training data, benchmarks and AUCs (TOUGH-M1, Vertex, ProSPECCTs), code URL and licence."}
```


**← tool result**

```
The server returned HTTP 403 Forbidden.

The response body was not retrieved. If this URL requires authentication, use an authenticated tool (e.g. `gh` for GitHub, or an MCP-provided fetch tool) instead of WebFetch.
```


**← tool result**

```
**Runtime** (2,000 comparisons on an AMD 2.4 GHz Opteron cluster, excluding input preparation):
- SiteEngine: "8983 seconds"
- APoc, pocket comparison alone: "73 seconds"
- APoc, pocket plus global structure comparison: "3686 seconds"

**Algorithm:** Your guess is partly right. The method has three stages:
1. It generates initial alignment guesses from gapless alignments, secondary structure comparison, fragment alignments, and local contact pattern alignments.
2. It iteratively applies "dynamic programming" to refine these into sequential alignments.
3. It searches for non-sequential matches by casting the problem as an assignment problem, which the authors describe as "a special case of integer programming." They solve it with a shortest-augmenting-path method, with O(N³) complexity.
```


**→ tool call `WebFetch`** · 2026-10-27 17:42:51

```
{"url": "https://github.com/BenevolentAI/DeeplyTough", "prompt": "Summarize: dependencies (fpocket, HTMD, Python version), licence text type, any runtime claims, benchmarks supported, whether maintained."}
```


**→ tool call `WebSearch`** · 2026-10-27 17:42:52

```
{"query": "DeeplyTough descriptor voxel grid TOUGH-M1 AUC ProSPECCTs Vertex alignment-free Euclidean distance runtime", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "DeeplyTough descriptor voxel grid TOUGH-M1 AUC ProSPECCTs Vertex alignment-free Euclidean distance runtime"

Links: [{"title":"Density-Wise Two Stage Mammogram Classification using Texture Exploiting Descriptors","url":"https://arxiv.org/pdf/1701.04010"},{"title":"The Morse Transform for Discrete Shape Analysis","url":"https://arxiv.org/pdf/2503.04507"},{"title":"BIRADS Features-Oriented Semi-supervised Deep Learning for Breast Ultrasound Computer-Aided Diagnosis","url":"https://arxiv.org/pdf/1904.01076"},{"title":"documentserver.uhasselt.be","url":"https://documentserver.uhasselt.be/bitstream/1942/30899/1/everaert.pdf"},{"title":"Method . | AUC . | AUPR . | MCC . | F1 . |","url":"https://dbpia.nl.go.kr/view-large/496137423"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC6175913/table/Tab2"},{"title":"1 code implementation • 23 Nov 2019 • Zexuan Sun, Shujun Huang, Peiran Jiang, Pingzhao Hu","url":"https://astro.paperswithcode.com/author/zexuan-sun"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10259651/table/T7"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10259651/table/T3"},{"title":"auc spec","url":"https://api.emergentmind.com/topics/auc-spec"}]

The search didn't return anything about DeeplyTough, its voxel-grid descriptor, TOUGH-M1, ProSPECCTs, or the runtime comparison. The results were about unrelated topics: mammogram classification,
… [541 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
**Dependencies**
- **Python:** The main `deeplytough` environment uses Python 3.6. A separate Python 2.7 environment handles protein structure preprocessing with MGLTools 1.5.6.
- **HTMD:** A legacy version (1.13.10) is built from source. The page doesn't say why a legacy version is needed.
- **fpocket2:** Required only for TOUGH-M1 preprocessing. It is compiled from source with a patched makefile.
- **Other:** OpenBabel (via apt), a pinned legacy se3cnn commit, lie_learn, and llvmlite 0.28. Local installation is described as Linux-only. A Dockerfile is provided, with an image of about 4.7 GB.

**Licence**
The "License Terms" section gives a copyright notice: "(c) BenevolentAI Limited 2019. All rights reserved." It directs licensing enquiries to an email address. The page links to a LICENCE file, but its text isn't included, so I can't identify a specific licence from this page.

**Runtime claims**
- It is described as the official PyTorch implementation of the authors' JCIM paper.
- Evaluation assumes a GPU and a 4-core CPU. CPU-only runs are supported with `--device 'cpu'`.
- Training needs a GPU with at least 11 GB of memory and reportedly takes about 1.5 days on recent hardware.
- The benchmark datasets require roughly 27 GB of storage.
- Results are non-deterministic, so the pre-trained networks can't be reproduced exactly.

**Benchmarks supported**
- TOUGH-M1
- Vertex
- ProSPECCTs
- Custom datasets, defined by a CSV file of pocket pairs

**Maintenance status**
The most 
… [244 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:43:09

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\nfor pmc in PMC10640396 PMC12343037 PMC12259003; do\ncurl -s \"https://www.ebi.ac.uk/europepmc/webservices/rest/$pmc/fullTextXML\" -o $pmc.xml; python3 - $pmc.xml <<'EOF'\nimport sys,re\nt=open(sys.argv[1]).read()\nt=re.sub(r'<[^>]+>',' ',t); t=re.sub(r'\\s+',' ',t)\nprint(sys.argv[1], len(t))\nfor m in re.finditer(r'[^.]{0,250}(second|minute|hour|\\bms\\b|CPU|GPU|core|licen)[^.]{0,200}\\.',t):\n    print(' -',m.group(0).strip()[:450])\nEOF\ndone 2>&1 | head -120", "description": "Extract runtime sentences from Europe PMC full texts"}
```


**← tool result**

```
PMC10640396.xml 24819
 - org/licenses/by/4.
 - org/licenses/by/4.
 - However, the bottleneck of the method is index creation, and pyScoMotif is able to perform motif searches in a few seconds, as shown in Supplementary Table S2 , which in absolute terms remains fast.
 - The method allows searching for such motifs in large sets of protein structures in seconds, which otherwise could take hours using a brute force method.
PMC12343037.xml 45731
 - org/licenses/by/4.
 - org/licenses/by/4.
 - anuscript no pmc-prop-legally-suppressed no pmc-prop-has-pdf yes pmc-prop-has-supplement yes pmc-prop-pdf-only no pmc-prop-suppress-copyright no pmc-prop-is-real-version no pmc-prop-is-scanned-article no pmc-prop-preprint no pmc-prop-in-epmc yes pmc-license-ref CC BY 1 Introduction Finding proteins with desired functions by mining databases is becoming increasingly attractive due to the growing amount of data and emerging computational tools.
 - The combination of mapped amino acids with the lowest score is then selected for the given structure.
 - Finally, the given structure is selected if its lowest score was less than user-defined value (default 1 Å).
 - Each running node in the cluster with 24 CPUs would process 10 000 proteins from the database in 2–10 min, with the exact duration depending on the average number of possible mappings to test.
 - Filtering was not possible for Strucmotif-search because the program provides only a score-sorted list of PDB proteins without detailed mapping 
… [5,062 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:43:19

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\nfor q in \"TrixP binding site\" \"BSSF ultrafast binding site\" \"PoSSuM pocket similarity sketches\" \"SiteMine binding site similarity\" \"RAPMAD pocket\" \"IsoMIF binding site molecular interaction field\" \"ProBiS local structural alignment binding sites\" \"eMatchSite\" \"Classification of protein-binding sites spherical convolutional\"; do\necho \"== $q\"; curl -s \"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=$(python3 -c \"import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))\" \"$q\")&format=json&pageSize=3&resultType=lite\" | python3 -c \"\nimport sys,json\nfor r in json.load(sys.stdin)['resultList']['result']:\n    print(' ',r.get('pmcid'),r.get('doi'),r.get('pubYear'),r.get('title','')[:100],r.get('isOpenAccess'))\"; done", "description": "Find PMC IDs via Europe PMC for runtime extraction"}
```


**← tool result**

```
Exit code 1
== TrixP binding site
Traceback (most recent call last):
  File "<string>", line 3, in <module>
KeyError: 'resultList'
== BSSF ultrafast binding site
Traceback (most recent call last):
  File "<string>", line 3, in <module>
KeyError: 'resultList'
== PoSSuM pocket similarity sketches
Traceback (most recent call last):
  File "<string>", line 3, in <module>
KeyError: 'resultList'
== SiteMine binding site similarity
Traceback (most recent call last):
  File "<string>", line 3, in <module>
KeyError: 'resultList'
== RAPMAD pocket
Traceback (most recent call last):
  File "<string>", line 3, in <module>
KeyError: 'resultList'
== IsoMIF binding site molecular interaction field
Traceback (most recent call last):
  File "<string>", line 3, in <module>
KeyError: 'resultList'
== ProBiS local structural alignment binding sites
Traceback (most recent call last):
  File "<string>", line 3, in <module>
KeyError: 'resultList'
== eMatchSite
Traceback (most recent call last):
  File "<string>", line 3, in <module>
KeyError: 'resultList'
== Classification of protein-binding sites spherical convolutional
Traceback (most recent call last):
  File "<string>", line 3, in <module>
KeyError: 'resultList'
```


**→ tool call `Bash`** · 2026-10-27 17:43:23

```
{"command": "curl -s \"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=TrixP&format=json&pageSize=3\" | head -c 600", "description": "Debug Europe PMC search response"}
```


**← tool result**

```
{"errCode":503,"errMsg":"Search service is temporarily unavailable. Please retry later."}
```


**→ tool call `Bash`** · 2026-10-27 17:43:31

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\nfor pmc in PMC3098077 PMC2639437 PMC9709917 PMC9549786 PMC4383952 PMC3980086 PMC9405584; do\ncurl -s \"https://www.ebi.ac.uk/europepmc/webservices/rest/$pmc/fullTextXML\" -o $pmc.xml; python3 - $pmc.xml <<'EOF'\nimport sys,re\nt=open(sys.argv[1]).read()\nt=re.sub(r'<[^>]+>',' ',t); t=re.sub(r'\\s+',' ',t)\nprint('=====',sys.argv[1], len(t), t[:150])\nfor m in re.finditer(r'[^.]{0,200}(seconds|minutes|hours| ms\\b|CPU time|per comparison|comparisons per|run ?time)[^.]{0,200}\\.',t):\n    print(' -',m.group(0).strip()[:400])\nEOF\ndone 2>&1 | head -150", "description": "Extract runtime statements from several PMC full texts"}
```


**← tool result**

```
===== PMC3098077.xml 52096  BMC Bioinformatics 13 bmcbioi 100965194 BMC Bioinformatics 1471-2105 BMC PMC3098077 PMC3098077.1 3098077 3098077 20100327 10.1186/1471-2105-11-47 147
===== PMC2639437.xml 54952  BMC Bioinformatics 13 bmcbioi 100965194 BMC Bioinformatics 1471-2105 BMC PMC2639437 PMC2639437.1 2639437 2639437 19091072 10.1186/1471-2105-9-543 147
 - A typical database search of a query site against those from a large dataset comprising about 20000 sites takes in the order of 4 minutes to complete on the same machine with MPI-C version using 4 processors.
===== PMC9709917.xml 76119  822 acssd Journal of Chemical Information and Modeling J Chem Inf Model PMC9709917 9709917 9709917 36341715 10.1021/acs.jcim.2c00832 Classification o
 - The authors used the da T aset t O eval U ate al G orit H ms for binding site M atching (TOUGH-M1) dataset 32 for training since it represents the largest binding-site pair dataset constructed to date.
 - The tasks include a classification and metric learning objective, trained and evaluated using established datasets: da T aset t O eval U ate al G orit H ms for binding site C lassification (TOUGH-C1) 31 and TOUGH-M1, 32 respectively.
===== PMC9549786.xml 71016  3944 nargab NAR Genomics and Bioinformatics NAR Genom Bioinform Oxford University Press PMC9549786 9549786 9549786 36225529 10.1093/nargab/lqac078 PD
===== PMC4383952.xml 25841  4 nar Nucleic Acids Research Nucleic Acids Res Oxford University Press PMC4383952 4383952 4383952 25404129
… [956 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:43:40

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\nfor f in PMC3098077 PMC4383952 PMC9549786 PMC9709917; do python3 - $f.xml <<'EOF'\nimport sys,re\nt=open(sys.argv[1]).read()\nt=re.sub(r'<[^>]+>',' ',t); t=re.sub(r'\\s+',' ',t)\nprint('=====',sys.argv[1])\nfor m in re.finditer(r'[^.]{0,200}(\\bsec\\b|second|minute|hour|fast|speed|pairs|AUC|time)[^.]{0,200}\\.',t):\n    s=m.group(0).strip()\n    if any(k in s for k in ['sec','minute','hour','pairs','AUC','speed']): print(' -',s[:350])\nEOF\ndone 2>&1 | head -80", "description": "Extract more speed statements from PMC texts"}
```


**← tool result**

```
===== PMC3098077.xml
 - algorithm of the scoring method, we calculated a new Fix_Num ij for each two binding sites: (2) Scores ( FP_Score ) below 100 (which indicate similar binding sites not representing random comparison pairs) were eliminated and remaining scores were stored into bins of Fix_Num ij (window length 0.
 - For the sake of generalization, we randomly selected 3000 binding sites from our binding site fingerprint database and calculated similarities for each pair (9,000,000 pairs).
 - After removing obviously similar pairs (FP_Score &lt; 100.
 - In this test, 11121, 4309, 1568 pairs of similar PDB entries were found at 1/3, 1/2 and 2/3 levels respectively.
 - As shown in Figure 7 , at low Z-score value, the similar pairs found indeed have high sequence similarity.
 - 0, about 80% predicted similar pairs are either contained in the same SCOP family or have the sequence blast E-value lower than 1E-10.
 - Also, the comparison shows that in several cases, the SuMo and geometric hashing method used in SitesBase fail to identify the similarity of the pairs.
 - After finishing this fast database search (normally about 1 minute), the result will appear in a table on the web page for inspection.
 - The time consumed to perform a single query with our binding site database (188959 entries after the binding sites smaller than 30 points or larger than 200 points being filtered) is approximately 1 minute on an Intel XEON 2.
===== PMC4383952.xml
 - Since its initial release in
… [8,279 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:43:47

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\npython3 - PMC9709917.xml <<'EOF'\nimport sys,re\nt=open(sys.argv[1]).read()\nt=re.sub(r'<[^>]+>',' ',t); t=re.sub(r'\\s+',' ',t)\nfor k in ['BindSiteS-CNN achieves a mean AUC','next best performing','github','DeepSphere','descriptor','Data and Software']:\n    for m in re.finditer(re.escape(k),t):\n        print('-',t[max(0,m.start()-200):m.start()+400]); print()\n        break\nEOF", "description": "Extract BindSiteS-CNN AUC and code details"}
```


**← tool result**

```
- . Using the combination of all spherical feature maps, BindSiteS-CNN was trained using the TOUGH-M1 dataset as described where the pocket is determined through the pocket prediction method FPocket. 9 BindSiteS-CNN achieves a mean AUC of 0.86 ± 0.003 compared to DeeplyTough 0.91 ± 0.003. Interestingly, when trained using the pocket defined as atoms within 6 Å of a bound ligand, the performance increases to AUC 0.89 ± 0.002, highlighting an increased sensitivity to the input pocket definition compared with volumetric methods. Compared with the next best performing methods, both deep learning-bas

- s within 6 Å of a bound ligand, the performance increases to AUC 0.89 ± 0.002, highlighting an increased sensitivity to the input pocket definition compared with volumetric methods. Compared with the next best performing methods, both deep learning-based methods significantly outperform other binding site similarity tools: SiteEngine (AUC 0.732), G-LoSA (0.694), PocketMatch (0.644), and APoc (0.644). As noted by Simonovsky and Meyers, 29 analysis of BindSiteS-CNN results indicate that false negatives and false positives may indicate questionable ground-truth labels in the dataset, where shared

- section. The method described here was implemented using Python 3.7 and the PyCharm Python Integrated Development Environment. The code and description of procedures are available on GitHub - https://github.com/Jing9558/BindSiteS-CNN Supplementary Material ci2c00832_si_001.pdf References M
… [1,518 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:43:56

```
{"query": "fused Gromov-Wasserstein protein binding pocket alignment similarity", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:43:56

```
{"query": "Polypharmacology rescored protein-ligand interaction profiles remote binding site similarity assessment PLIP Salentin", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:43:57

```
{"query": "SiteContext Bhatti Singh transportation Sinkhorn binding site comparison runtime", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "SiteContext Bhatti Singh transportation Sinkhorn binding site comparison runtime"

Links: [{"title":"Site2Vec: a reference frame invariant algorithm for vector embedding of protein-ligand binding sites","url":"https://arxiv.org/pdf/2003.08149"},{"title":"A benchmark driven guide to binding site comparison: An exhaustive evaluation using tailor-made data sets (ProSPECCTs)","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6224041/"},{"title":"PocketMatch: A new algorithm to compare binding sites in protein structures","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2639437/"},{"title":"tintin.cs.uiowa.edu","url":"https://tintin.cs.uiowa.edu/SiteContext/about"},{"title":"Journal article","url":"https://iro.uiowa.edu/esploro/outputs/journalArticle/SiteContext-A-Web-Server-for-Protein/9985152240602771"},{"title":"visual sample binding","url":"https://tintin.cs.uiowa.edu/SiteContext/visual-sample-binding"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/313615"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/pmid/30408032"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC2639437"},{"title":"core.ac.uk","url":"https://core.ac.uk/works/60994216"}]

The search found the SiteContext paper and project pages, but no runtime figures for SiteContext itself.

- **What SiteContext is:** It's a web server for comparing protein binding sites, published in the Journal of Molecular Biology i
… [1,474 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "Polypharmacology rescored protein-ligand interaction profiles remote binding site similarity assessment PLIP Salentin"

Links: [{"title":"PLIP: fully automated protein–ligand interaction profiler","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4489249/"},{"title":"Supported Applications","url":"https://sbgrid.org/software/titles/plip"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC8262720"},{"title":"tu-dresden.de","url":"https://tu-dresden.de/ing/informatik/ressourcen/dateien/postgraduales/archiv/6036d3280fceb3cb4d90f03c59e03b2a.pdf"},{"title":"bioinformaticshome.com","url":"https://bioinformaticshome.com/db/tool/plip"},{"title":"Commit f1d204c2 authored by Steffen Möller's avatar Steffen Möller","url":"https://salsa.debian.org/med-team/plip/commit/f1d204c2cf2378fa4742a19902af2d5f802cb1eb"},{"title":"manpages.org","url":"https://manpages.org/plipcmd"},{"title":"PLIPify (WIP)","url":"https://volkamerlab.org/projects/plipify/"},{"title":"the structural basis of drugs targeting proteinprotein interactions uncovered with the proteinligand interaction profiler plip(f78cd8dd 970c 4865 8682 b22caf0d8f79)","url":"https://fis.tu-dresden.de/portal/de/publications/the-structural-basis-of-drugs-targeting-proteinprotein-interactions-uncovered-with-the-proteinligand-interaction-profiler-plip(f78cd8dd-970c-4865-8682-b22caf0d8f79).html"},{"title":"the structural basis of drugs targeting proteinprotein interactions uncover
… [2,047 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "fused Gromov-Wasserstein protein binding pocket alignment similarity"

Links: [{"title":"A new protein binding pocket similarity measure based on comparison of clouds of atoms in 3D: application to ligand prediction","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2838872/"},{"title":"A new protein binding pocket similarity measure based on comparison of 3D atom clouds: application to ligand prediction","url":"https://arxiv.org/pdf/0907.1531"},{"title":"GW protein","url":"https://gwprot.readthedocs.io/en/latest/GW_protein.html"},{"title":"Fused Gromov-Wasserstein Correspondences","url":"https://gwprot.readthedocs.io/en/latest/fused_gromov_wasserstein.html"},{"title":"UniOTalign: A Global Matching Framework for Protein Alignment via Optimal Transport","url":"https://arxiv.org/html/2510.06554v1"},{"title":"close this message","url":"https://arxiv.org/abs/2510.06554v1"},{"title":"Example 3: Clustering based on structural similarity","url":"https://gwprot.readthedocs.io/en/latest/Examples/Example_3_Clustering_RdRps.html"},{"title":"gwprot.readthedocs.io","url":"https://gwprot.readthedocs.io/en/latest/_sources/index.rst.txt"},{"title":"Example 3 Clustering RdRps.ipynb","url":"https://gwprot.readthedocs.io/en/latest/_sources/Examples/Example_3_Clustering_RdRps.ipynb.txt"},{"title":"arxiv.org","url":"https://arxiv.org/abs/2509.01550v1"}]

The search didn't turn up a paper that applies fused Gromov-Wasserstein (FGW) specifically to binding-pocket al
… [2,044 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:44:16

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\ncat > q5.txt <<'EOF'\nPolypharmacology rescored protein-ligand interaction profiles for remote binding site similarity assessment\nA new protein binding pocket similarity measure based on comparison of clouds of atoms in 3D application to ligand prediction\nDeciphering interaction fingerprints from protein molecular surfaces bioRxiv Gainza 2019\nPatch-Surfer2.0 fast protein binding pocket comparison\nPL-PatchSurfer\nLIGSITEcsc SitesBase geometric hashing binding site Gold Jackson\nEOF\npython3 cr.py < q5.txt\nfor pmc in PMC2838872; do curl -s \"https://www.ebi.ac.uk/europepmc/webservices/rest/$pmc/fullTextXML\" -o $pmc.xml; python3 - $pmc.xml <<'EOF'\nimport sys,re\nt=open(sys.argv[1]).read()\nt=re.sub(r'<[^>]+>',' ',t); t=re.sub(r'\\s+',' ',t)\nprint(len(t),t[:200])\nfor m in re.finditer(r'[^.]{0,200}(second|minute|hour|time)[^.]{0,200}\\.',t): print(' -',m.group(0)[:300])\nEOF\ndone", "description": "Fifth Crossref batch and sweet-kernel runtime", "timeout": 200000}
```


**← tool result**

```
Polypharmacology rescored protein-ligand | 10.1016/j.pbiomolbio.2014.05.006 | Polypharmacology rescored: Protein–ligand interaction profiles for remote binding site sim | Progress in Biophysics and Molecular Bio | 2014 | Salentin
Polypharmacology rescored protein-ligand | 10.1007/s10930-013-9494-1 | Ligand Binding Site Similarity Identification Based on Chemical and Geometric Similarity | The Protein Journal | 2013 | Tu
A new protein binding pocket similarity  | 10.1186/1471-2105-11-99 | A new protein binding pocket similarity measure based on comparison of clouds of atoms in  | BMC Bioinformatics | 2010 | Hoffmann
A new protein binding pocket similarity  | 10.1021/acs.jcim.9b00717.s001 | DStruBTarget: Integrating Binding Affinity with Structure Similarity for Ligand-Binding Pr |  | None | ?
Deciphering interaction fingerprints fro | 10.1101/606202 | Deciphering interaction fingerprints from protein molecular surfaces |  | 2019 | Gainza
Deciphering interaction fingerprints fro | 10.1038/s41592-019-0666-6 | Deciphering interaction fingerprints from protein molecular surfaces using geometric deep  | Nature Methods | 2019 | Gainza
Patch-Surfer2.0 fast protein binding poc | 10.2142/biophys.53.s203_3 | 2P268 Protein binding pocket and ligand shape comparison(22A. Bioinformatics: Structural g | Seibutsu Butsuri | 2013 | Motono
Patch-Surfer2.0 fast protein binding poc | 10.7717/peerj.4962/fig-6 | Figure 6: Binding pocket of target protein. |  | None | ?
PL-PatchSurfer               
… [2,399 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebFetch`** · 2026-10-27 17:44:33

```
{"url": "https://www.biorxiv.org/content/10.1101/606202v1.full", "prompt": "For MaSIF-search and MaSIF-ligand: quote runtime numbers (fingerprint computation time, comparison time, scanning time for large decoy set, comparison to ZDOCK/PatchDock) and performance (MaSIF-ligand balanced accuracy, number of ligand classes; MaSIF-search ranking). Patch radius and descriptor length."}
```


**← tool result**

```
**MaSIF-ligand**
- **Task:** Classifies pockets into seven cofactor classes (ADP, NAD, NADP, FAD, SAM, CoA, HEME). Random expected balanced accuracy is 0.14.
- **Performance:** Balanced accuracy is 0.73 with all features, 0.65 with chemical features only, and 0.55 with geometric features only. Overall accuracy is 0.78.
- **Patch radius:** 12 Å.
- **Descriptor length:** 80-dimensional fingerprint.
- **Runtime:** Not reported.

**MaSIF-search**
- **Patch radius:** 9 Å or 12 Å depending on application. The second-stage alignment used 9 Å patches "To optimize speed."
- **Descriptor length:** 80-dimensional fingerprint.
- **Fingerprint computation:** Precomputation for a 100-residue protein takes about 2 minutes, on CPUs. The paper does not give a separate figure for fingerprint computation.
- **Scanning and comparison (bound benchmark, 100 complexes):**
  - PatchDock: 40 solved, 2854 minutes.
  - MaSIF-search, K=100: 41 solved, 2 minutes (excluding precomputation).
  - MaSIF-search, K=3000: 62 solved, 17 minutes.
  - GIF with the same second stage: 9 solved.
- **Apo benchmark (40 complexes, top 1000):**
  - PatchDock: 11 solved, 1045 minutes.
  - MaSIF-search, K=1000: 14 solved, 4 minutes.
  - MaSIF-search, K=3000: 17 solved, 11 minutes.
  - GIF: 3 solved.
- **Large decoy scan (PD-1/PD-L1):** About 11,000 structures (52 million descriptors) scanned in 26 minutes. The mouse PD-1 ranked #1, #3 and #4, and the human PD-1 ranked #8.
- **Discrimination:** ROC AUC of 0.99 on the test s
… [337 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:44:55

```
{"command": "curl -s \"https://api.github.com/users/insilab/repos?per_page=50\" | python3 -c \"import sys,json;d=json.load(sys.stdin);[print(i['full_name'],(i.get('license') or {}).get('spdx_id'),i['pushed_at'][:10],(i.get('description') or '')[:70]) for i in d] if isinstance(d,list) else print(d)\"\nsleep 3\ncurl -s \"https://api.github.com/search/repositories?q=probis+binding+site&per_page=5\" | python3 -c \"import sys,json;d=json.load(sys.stdin);[print(i['full_name'],(i.get('license') or {}).get('spdx_id'),i['pushed_at'][:10],(i.get('description') or '')[:70]) for i in d.get('items',[])]\"\nsleep 3\nfor r in Jing9558/BindSiteS-CNN sbnb-irb/PocketVec IDEA-XL/LigUnity bowen-gao/ProFSA klemens-floege/oneprot JingHuangLab/ErePOC tiantz17/PocketAnchor anjie-qiao/BindCLIP mtthchrtr/IsoMif 1337deepesh/PocketMatch_v2.0 michal-brylinski/ematchsite FreyrS/dMaSIF; do curl -s https://api.github.com/repos/$r | python3 -c \"import sys,json;d=json.load(sys.stdin);print('$r', (d.get('license') or {}).get('spdx_id'), (d.get('pushed_at') or '')[:10], d.get('stargazers_count'))\"; done", "description": "Check more GitHub repos and licences"}
```


**← tool result**

```
Jing9558/BindSiteS-CNN MIT 2022-09-27 9
sbnb-irb/PocketVec MIT 2026-10-05 13
IDEA-XL/LigUnity Apache-2.0 2026-03-30 63
bowen-gao/ProFSA MIT 2024-06-03 23
klemens-floege/oneprot None 2026-06-30 25
JingHuangLab/ErePOC None 2025-12-17 4
tiantz17/PocketAnchor Apache-2.0 2023-08-17 36
anjie-qiao/BindCLIP MIT 2026-08-13 11
mtthchrtr/IsoMif None 2016-05-07 5
1337deepesh/PocketMatch_v2.0 None 2015-05-12 9
michal-brylinski/ematchsite None 2017-03-10 2
FreyrS/dMaSIF NOASSERTION 2023-05-22 257
```


**→ tool call `WebFetch`** · 2026-10-27 17:45:09

```
{"url": "http://insilab.org/probis-algorithm/", "prompt": "What is the download/licence status of the ProBiS standalone program? Any runtime numbers? Any GitHub link?"}
```


**→ tool call `WebFetch`** · 2026-10-27 17:45:10

```
{"url": "https://www.zbh.uni-hamburg.de/forschung/amd/software/sitemine.html", "prompt": "Quote runtime numbers, licence, download format (binary?), relation to GeoMine, and whether it handles AlphaFold/predicted sites."}
```


**← tool result**

```
proxy refused the connection
```


**← tool result**

```
- **Runtime:** "SiteMine runs take approx. three minutes on a database of 10,000 pockets."
- **Licence:** The page doesn't name a licence. It says the command-line tool is "freely available for non-commercial and academic users" on Linux, macOS, and Windows, and that "Non-academic users can get an evaluation license free of charge."
- **Download format:** The page doesn't say whether the download is a binary or source code. It notes that "The download includes detailed documentation for generating individual Postgres databases," and that you must register first.
- **GeoMine:** SiteMine can "screen large GeoMine databases of ligand-based and/or predicted binding sites" for sites similar to a modeled query site.
- **AlphaFold/predicted sites:** The page doesn't mention AlphaFold. It does say users "can create databases of individual experimental or predicted structures," so predicted structures are supported in principle.
```


**→ tool call `WebSearch`** · 2026-10-27 17:45:22

```
{"query": "3D-AF-Surfer AlphaFold Zernike descriptors real-time search Kihara", "mode": "standard"}
```


**→ tool call `WebSearch`** · 2026-10-27 17:45:23

```
{"query": "G-LoSA runtime per alignment seconds Lee Im ligand binding site alignment iterative maximum clique", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "G-LoSA runtime per alignment seconds Lee Im ligand binding site alignment iterative maximum clique"

Links: [{"title":"Comparative assessment of strategies to identify similar ligand-binding pockets in proteins","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5845264/"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC4941214"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3478504"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC5845264"},{"title":"13eebf66 35f7 428b abfc 144c9f7e0d41","url":"https://kuscholarworks.ku.edu/entities/publication/13eebf66-35f7-428b-abfc-144c9f7e0d41"},{"title":"compbio.lehigh.edu","url":"https://compbio.lehigh.edu/GLoSA"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC3821077"},{"title":"s12859 018 2109 2","url":"https://link.springer.com/doi/10.1186/s12859-018-2109-2"},{"title":"Lee 2013","url":"https://kuscholarworks.ku.edu/bitstream/1808/24230/1/Lee_2013.pdf"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/268565v1"}]

The search did not turn up a per-alignment runtime for G-LoSA. The results describe the method but give no timing figures.

- **Method:** G-LoSA builds binding-site alignments using iterative maximum clique search and fragment superimposition. G-LoSA has been developed to construct binding site alignments with iterative maximum clique sear
… [947 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
Web search results for query: "3D-AF-Surfer AlphaFold Zernike descriptors real-time search Kihara"

Links: [{"title":"Real-Time Structure Search and Structure Classification for AlphaFold Protein Models","url":"https://www.biorxiv.org/content/10.1101/2021.10.21.465371.full.pdf"},{"title":"Real-time structure search and structure classification for AlphaFold protein models","url":"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8983703/"},{"title":"www.biorxiv.org","url":"https://www.biorxiv.org/content/10.1101/2021.10.21.465371v2.full.pdf+html"},{"title":"pmc.ncbi.nlm.nih.gov","url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC8983703"},{"title":"Real-time structure search and structure classification for AlphaFold protein models","url":"https://communities.springernature.com/posts/real-time-structure-search-and-structure-classification-for-alphafold-protein-models"},{"title":"Behind the Paper","url":"https://communities.springernature.com/amp/posts/real-time-structure-search-and-structure-classification-for-alphafold-protein-models"},{"title":"3d surfer","url":"https://kiharalab.org/3d-surfer/"},{"title":"Real-time structure search and structure classification for AlphaFold protein models","url":"https://pubmed.ncbi.nlm.nih.gov/35383281/"},{"title":"kiharalab.org","url":"https://kiharalab.org/3d-surfer/index.php"},{"title":"cbe.snu.ac.kr","url":"https://cbe.snu.ac.kr/%ea%b3%b5%ed%86%b5-%ea%b3%b5%ec%a7%80/document/6609"}]

3D-AF-Surfer is a Kihara lab web server for real-time struc
… [1,575 more characters; full text in agent_logs/raw/]
```


**→ tool call `Bash`** · 2026-10-27 17:45:36

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\nprintf \"Lee Im 2013 ligand binding site alignment G-LoSA Journal of Chemical Information and Modeling iterative maximum clique\\nReal-time structure search and structure classification for AlphaFold protein models Aderinwale\\n\" | python3 cr.py\nfor pmc in PMC3821077 PMC4941214; do curl -s \"https://www.ebi.ac.uk/europepmc/webservices/rest/$pmc/fullTextXML\" -o $pmc.xml; python3 - $pmc.xml <<'EOF'\nimport sys,re\nt=open(sys.argv[1]).read()\nt=re.sub(r'<[^>]+>',' ',t); t=re.sub(r'\\s+',' ',t)\nprint('==',sys.argv[1],len(t),t[:200])\nfor m in re.finditer(r'[^.]{0,250}(seconds|minutes|hours|CPU time|computational time|computing time|run ?time)[^.]{0,250}\\.',t): print(' -',m.group(0)[:450])\nEOF\ndone", "description": "G-LoSA DOI and runtime from PMC", "timeout": 200000}
```


**← tool result**

```
Lee Im 2013 ligand binding site alignmen | 10.1021/ci4003602 | Ligand Binding Site Detection by Local Structure Alignment and Its Performance Complementa | Journal of Chemical Information and Mode | 2013 | Lee
Lee Im 2013 ligand binding site alignmen | 10.1021/acs.jcim.9b01143 | Combinatorial Effect of Ligand and Ligand-Binding Site Hydrophobicities on Binding Affinit | Journal of Chemical Information and Mode | 2020 | Sriramulu
Real-time structure search and structure | 10.1101/2021.10.21.465371 | Real-Time Structure Search and Structure Classification for AlphaFold Protein Models |  | 2021 | Aderinwale
Real-time structure search and structure | 10.1038/s42003-022-03261-8 | Real-time structure search and structure classification for AlphaFold protein models | Communications Biology | 2022 | Aderinwale
== PMC3821077.xml 150 {"timestamp":"2026-10-27T17:45:41.382+00:00","status":500,"error":"Internal Server Error","path":"/europepmc/webservices/rest/PMC3821077/fullTextXML"}
== PMC4941214.xml 150 {"timestamp":"2026-10-27T17:45:41.638+00:00","status":500,"error":"Internal Server Error","path":"/europepmc/webservices/rest/PMC4941214/fullTextXML"}
```


**→ tool call `Bash`** · 2026-10-27 17:45:54

```
{"command": "cd /tmp/claude-548918/-cluster-project-beltrao-gmagnus-pocket-compare/6040d382-46cf-4eb9-aabc-b618c60a25da/scratchpad\nprintf \"PocketGraph graph representation of binding site volumes Weisel Schneider\\nPSIM pocket similarity search\\nSiteMotif binding site motif alignment\\nLabelHash algorithm substructure matching\\nTIFP triplet interaction fingerprint\\n\" | python3 cr.py", "description": "Crossref for PocketGraph and misc", "timeout": 120000}
```


**← tool result**

```
PocketGraph graph representation of bind | 10.1186/1752-153x-3-s1-p66 | PocketGraph: graph representation of binding site volumes | Chemistry Central Journal | 2009 | Weisel
PocketGraph graph representation of bind | 10.1021/acs.jcim.3c01698.s001 | Graph Attention Site Prediction (GrASP): Identifying Druggable Binding Sites Using Graph N |  | None | ?
PSIM pocket similarity search            | 10.26434/chemrxiv.12722483.v1 | COVID19 Approved Drug Repurposing: Pocket Similarity Approach |  | 2020 | Fadlalla
PSIM pocket similarity search            | 10.1186/1758-2946-4-18 | FragVLib a free database mining software for generating "Fragment-based Virtual Library" u | Journal of Cheminformatics | 2012 | Khashan
SiteMotif binding site motif alignment   | 10.1007/978-1-4614-1533-6_100170 | Binding Site: Binding Motif | Encyclopedia of Metalloproteins | 2013 | ?
SiteMotif binding site motif alignment   | 10.1021/bi500891d.s002 | Thermodynamic Characterization of the DmsD Binding Site for the DmsA Twin-Arginine Motif |  | None | ?
LabelHash algorithm substructure matchin | 10.1186/1471-2105-11-555 | The LabelHash algorithm for substructure matching | BMC Bioinformatics | 2010 | Moll
LabelHash algorithm substructure matchin | 10.1038/npre.2008.2199.1 | LabelHash: A Flexible and Extensible Method for Matching Structural Motifs | Nature Precedings | 2008 | Moll
TIFP triplet interaction fingerprint     | 10.1021/acsami.3c05473.s001 | Tamm Plasmon Resonance as Optical Fingerprint of Silve
… [200 more characters; full text in agent_logs/raw/]
```


**→ tool call `WebSearch`** · 2026-10-27 17:47:00

```
{"query": "FuzCav alignment-free ultra-high-throughput comparison druggable binding sites 4833 integers fingerprint", "mode": "standard"}
```


**← tool result**

```
Web search results for query: "FuzCav alignment-free ultra-high-throughput comparison druggable binding sites 4833 integers fingerprint"

Links: [{"title":"Implementation of functions in R tool in parallel environment","url":"https://arxiv.org/pdf/1905.06237"},{"title":"Alignment-Free Ultra-High-Throughput Comparison of Druggable Protein−Ligand Binding Sites","url":"https://lab.drugdesign.unistra.fr/publications/2010_weill/"},{"title":"drugdesign.unistra.fr","url":"https://drugdesign.unistra.fr/lab/publications/paper116.pdf"},{"title":"A simple and fuzzy method to align and compare druggable ligand-binding sites","url":"https://lab.drugdesign.unistra.fr/publications/2008_schalon/"},{"title":"Encoding Protein–Ligand Interaction Patterns in Fingerprints and Graphs","url":"https://lab.drugdesign.unistra.fr/publications/2013_desaphy/"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/2003.08149v1.pdf"},{"title":"arxiv.org","url":"https://arxiv.org/pdf/2003.08149v2"},{"title":"Computational and Structural Biotechnology Journal (Jun 2014)","url":"https://doaj.org/article/d2f3d482d4164797af10ab7356422ab8"},{"title":"A simple and fuzzy method to align and compare druggable ligand-binding sites","url":"https://lab.drugdesign.unistra.fr/tags/ligand/"},{"title":"Binding Site","url":"https://lab.drugdesign.unistra.fr/tags/binding-site/"}]

FuzCav is an alignment-free method by Weill and Rognan (Journal of Chemical Information and Modeling, 2010) for comparing druggable protein-ligand bi
… [1,915 more characters; full text in agent_logs/raw/]
```


**→ tool call `SubagentHandback`** · 2026-10-27 17:49:00

```
{"message": "# Catalog of binding-pocket similarity methods (literature review input)\n\n**How this was checked.** DOIs come from Crossref API lookups. Licences, last-push dates and pip/conda status come from the GitHub, PyPI and Anaconda APIs, queried 2026-10-27. Runtimes are quoted from primary text where I could read it. Anything labelled \"(secondary)\" came from a search-engine summary or third-party page, not the paper itself. \"My arithmetic\" marks a throughput I derived. \"unknown\" means I found no number.\n\n## 0. Benchmarks and the runtime yardstick\n- **ProSPECCTs** (Ehrt, Brinkjost & Koch 2018, PLoS Comput Biol, 10.1371/journal.pcbi.1006483). Table 6 gives average time per comparison on one core of a Xeon E5-2690 (2.9 GHz), dataset 5 (100 structures, 10k pairs):\n\n  | Method | Time per comparison (s) |\n  |---|---|\n  | PocketMatch | 0.000028 |\n  | KRIPO | 0.000092 |\n  | RAPMAD | 0.000285 |\n  | FuzCav | 0.000607 |\n  | TM-align | 0.0066 |\n  | Shaper | 0.0398 |\n  | VolSite/Shaper | 0.0431 |\n  | ProBiS | 0.0479 |\n  | TIFP | 0.0929 |\n  | Grim | 0.186–0.233 |\n  | IsoMIF | 0.256 |\n  | SiteHopper | 0.383 |\n  | Cavbase | 2.64 |\n  | SMAP | 4.23 |\n  | SiteEngine | 8.12 |\n  | SiteAlign | 28.6 |\n\n  - The authors' example: one site against all of sc-PDB (9,283 sites) takes 0.28 s with PocketMatch and about 3 days with SiteAlign.\n  - Treat these as comparison-step times. I did not verify whether descriptor generation is included.\n  - No single tool won. Is
… [26,989 more characters; full text in agent_logs/raw/]
```


**← tool result**

```
{"success":true,"message":"Report delivered to your caller."}
```
