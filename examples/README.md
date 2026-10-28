# Example structures

| file | content | source and licence |
|---|---|---|
| `pdb/1a28_A.pdb` | progesterone receptor ligand-binding domain, PDB 1A28 chain A, polymer atoms only (ligands, waters, altlocs removed) | wwPDB entry 1A28 (CC0 1.0); copied unchanged from the BURROW release `examples/` |
| `pdb/1a28_STR.pdb` | progesterone (STR) bound to chain A of 1A28, 23 heavy atoms (HETATM records) | wwPDB entry 1A28 (CC0 1.0); extracted for pocketcompare |
| `afdb/AF-P06401-F1-model_v6.cif.gz` | AlphaFold model of the human progesterone receptor (P06401, full length) | AlphaFold DB v6 (CC BY 4.0) |
| `afdb/AF-P00918-F1-model_v6.cif.gz` | AlphaFold model of human carbonic anhydrase 2 (P00918) | AlphaFold DB v6 (CC BY 4.0); copied unchanged from the BURROW release `examples/` |

The crystal structure with its ligand and the AlphaFold model of the same receptor form a holo / predicted pair: the
progesterone site of 1A28 retrieves the steroid pocket of the AlphaFold model first (cosine 0.986, next pocket 0.28),
while all carbonic anhydrase pockets score < 0. `quickstart.sh` (CLI) and `quickstart.py` (Python API) walk through
describe → compare → index → search; outputs go to `examples/out/` (git-ignored).
