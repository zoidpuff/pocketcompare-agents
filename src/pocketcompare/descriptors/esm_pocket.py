"""B4: ESM-2 (650M) pocket embedding = mean of per-residue embeddings over the pocket's lining residues.

* Sequence per chain is read from the structure file with gemmi (amino-acid residues in file order, first
  altloc, waters/ligands ignored; unknown residue -> X).  Lining residues use author numbering
  ``chain:resnum[icode]`` and are mapped to sequence indices through the gemmi residue list, never by
  assuming numbering starts at 1.  If the chain letter is absent and the file has exactly one protein chain
  (the adapter's single-chain remap, see reports/pocket_adapter.md) that chain is used.
* Chains are embedded separately.  Chains > 1022 residues: windows of 1022 with stride 511 (overlap 511,
  last window aligned to the chain end); per-residue embeddings are averaged over all windows covering them.
* Embedding = last hidden layer (after final layer norm), BOS/EOS removed, cached as fp16 per unique sequence
  (sha1 of sequence) under data/processed/esm/<model>/<sha1>.npy, so identical chains are shared.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

MODEL = "facebook/esm2_t33_650M_UR50D"
MODEL_TAG = "esm2_t33_650M_UR50D"
MAXLEN = 1022
STRIDE = 511
DIM = 1280


def chain_residues(path) -> dict:
    """{chain: (sequence, [resid strings 'num[icode]'])} for amino-acid residues of model 1."""
    import gemmi
    st = gemmi.read_structure(str(path))
    st.setup_entities()
    out = {}
    for ch in st[0]:
        seq, ids = [], []
        for r in ch:
            info = gemmi.find_tabulated_residue(r.name)
            if info is None or not info.is_amino_acid():
                continue
            ol = info.one_letter_code.upper()
            seq.append(ol if ol.isalpha() else "X")
            ids.append(f"{r.seqid.num}{r.seqid.icode.strip()}")
        if seq:
            out[ch.name] = ("".join(seq), ids)
    return out


def seq_key(seq: str) -> str:
    return hashlib.sha1(seq.encode()).hexdigest()


def window_starts(n: int, maxlen: int = MAXLEN, stride: int = STRIDE) -> list:
    if n <= maxlen:
        return [0]
    starts = list(range(0, n - maxlen + 1, stride))
    if starts[-1] != n - maxlen:
        starts.append(n - maxlen)
    return starts


class ESMEmbedder:
    def __init__(self, device="cuda", cache_dir="data/processed/esm", model_name=MODEL):
        import torch
        from transformers import AutoTokenizer, EsmModel
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = EsmModel.from_pretrained(model_name, add_pooling_layer=False).to(device).half().eval()
        self.device = device
        self.cache = Path(cache_dir) / MODEL_TAG
        self.cache.mkdir(parents=True, exist_ok=True)

    @property
    def _tmp(self):
        return self.torch.no_grad()

    def _embed_window(self, seq: str) -> np.ndarray:
        t = self.torch
        enc = self.tok(seq, return_tensors="pt", add_special_tokens=True).to(self.device)
        with t.no_grad():
            h = self.model(**enc).last_hidden_state[0, 1:-1]
        return h.float().cpu().numpy()

    def embed_chain(self, seq: str) -> np.ndarray:
        """(L,1280) float16, cached by sequence hash."""
        f = self.cache / f"{seq_key(seq)}.npy"
        if f.exists():
            return np.load(f)
        n = len(seq)
        if n <= MAXLEN:
            emb = self._embed_window(seq)
        else:
            acc = np.zeros((n, DIM), np.float32)
            cnt = np.zeros(n, np.float32)
            for s in window_starts(n):
                acc[s:s + MAXLEN] += self._embed_window(seq[s:s + MAXLEN])
                cnt[s:s + MAXLEN] += 1
            emb = acc / cnt[:, None]
        emb = emb.astype(np.float16)
        tmp = f.with_suffix(".tmp.npy")
        np.save(tmp, emb)
        tmp.replace(f)
        return emb


def pool_pocket(chains: dict, embs: dict, residues) -> tuple[np.ndarray | None, int, int]:
    """Mean over lining residues ``'chain:num[icode]'`` -> (vec float32 or None, n_found, n_missing).
    ``chains``: output of chain_residues; ``embs``: {chain: (L,D) array}."""
    rows = []
    miss = 0
    single = next(iter(chains)) if len(chains) == 1 else None
    maps = {c: {rid: i for i, rid in enumerate(v[1])} for c, v in chains.items()}
    for r in residues:
        ch, _, num = r.partition(":")
        c = ch if ch in chains else single
        if c is None or num not in maps[c]:
            miss += 1
            continue
        rows.append(embs[c][maps[c][num]].astype(np.float32))
    if not rows:
        return None, 0, miss
    return np.mean(rows, 0), len(rows), miss
