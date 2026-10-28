"""Fast-backend adapter: the same ``Featurized`` object as ``pockets.featurize_structure``, built from BURROW's
fast backend (``pocketdetect.burrow.fast``: Numba CPU or batched GPU featurisation; validated against the reference
implementation by BURROW's own tests and by ``tests/test_cli.py`` here).

    fm = fast_model()                                     # the pinned BURROW model, flat forests
    it, info = load_and_prep(path, key, af_mode=True)     # CPU worker: parse, AF pruning, host-side prep
    (ps, score), = featurize_batch([it], fm.cfg, "cuda:0", fm)      # GPU (pocketdetect.burrow.fast.gpu)
    fs = featurized_from_points(it.P, ps, score, fm, key)           # CPU worker: formation, ranking, rules
    fs = featurize_fast_cpu(path, key, af_mode=True)      # one structure, Numba CPU path end-to-end

Differences from the reference adapter: hetero atoms are not kept (so ``--ligand`` sites given by a ligand that is
part of the structure file need the reference backend) and ``meta['structure_sha256']`` is not computed.
"""
from __future__ import annotations

import dataclasses
import functools
import json
import time

import numpy as np

from .pockets import (ADAPTER_VERSION, REGION_RULE, Featurized, _res_names, _sha256, _STR, burrow_version,
                      model_path, sort_residues)

FAST_ADAPTER_VERSION = "pockets-fast-v1"


@functools.lru_cache(maxsize=None)
def fast_model():
    from pocketdetect.burrow.fast.pipeline import FastModel
    return FastModel.load(str(model_path()))


def load_protein_af(path, key: str, af_mode: bool = True, chains=None):
    """(Protein, weights|None, residue pLDDT dict {res_id: pLDDT} of the FULL model, n_res_pruned).
    ``chains``: author chain ids to keep (None = all protein chains of the first model)."""
    from pocketdetect.burrow.af import af_protein, residue_plddt
    from pocketdetect.burrow.prep import protein_from_structure
    from pocketdetect.structure import load_structure
    s = load_structure(str(path), structure_id=key, chains=list(chains) if chains is not None else None)
    sp = s.select(s.protein_heavy_mask())
    pl = residue_plddt(sp).astype(np.float32)
    pld = dict(zip(sp.residue_ids.tolist(), pl.tolist()))
    if af_mode:
        P, w, st = af_protein(s)
        return P, w, pld, int(st["n_res_pruned"])
    return protein_from_structure(s), None, pld, 0


def load_and_prep(path, key: str, af_mode: bool = True, fm=None, chains=None):
    """CPU-side parse + AF pruning + GPU-batch preparation (``fast.gpu.prep``).  Returns (Prepped, info)."""
    from pocketdetect.burrow.fast.gpu import prep
    fm = fm or fast_model()
    t0 = time.perf_counter()
    P, w, pld, npr = load_protein_af(path, key, af_mode, chains)
    t1 = time.perf_counter()
    it = prep(P, fm.cfg, w)
    t2 = time.perf_counter()
    return it, dict(plddt=pld, n_res_pruned=npr, parse_s=t1 - t0, prep_s=t2 - t1)


def featurized_from_points(P, ps, score, fm, key: str, af_mode: bool = True, extra_meta: dict | None = None
                           ) -> Featurized:
    """Everything after the point features, as ``pockets.featurize_structure``: full list (``min_score=None``)
    + v2/region flags; ``score`` = point scores from the GPU (None -> computed here on the CPU)."""
    from pocketdetect.burrow.fast import formation as FF
    from pocketdetect.burrow.fast.guard import stage_ok
    from pocketdetect.burrow.fast.pipeline import _output_residues, geo_values, score_points
    from pocketdetect.burrow.fast.pocketfeat import pocket_features, residue_chains
    from pocketdetect.burrow.output_rules import apply_rule

    bad = [s for s in ("features", "formation", "pocket_features", "scoring") if not stage_ok(s)]
    if bad:
        raise RuntimeError(f"BURROW fast stages not validated against the reference: {bad}")
    if any(fm.model.meta.get(k) for k in ("context", "apo_feats", "propensity")):
        raise NotImplementedError("ranker extras not supported by the fast adapter")
    t0 = time.perf_counter()
    fc = dataclasses.replace(fm.fc, min_score=None)
    names = list(ps.names)
    if score is None:
        score = score_points(fm, ps.feats, names)
    score = np.asarray(score, np.float32)
    gv = geo_values(ps.feats, names)
    is_metal = ps.feats[:, names.index("metal_cand")] > 0
    c = FF.candidates(ps.X, ps.points, ps.vol, gv, score, is_metal, fc)
    FF.assign_residues(c, ps.points, P.coords, P.res_index, len(P.residue_ids))
    if len(c):
        rch, nch = residue_chains(P.residue_ids)
        Fp, fn = pocket_features(c, ps.X, ps.vol, ps.feats, names, score, len(P.coords), rch, nch)
        rs = fm.rank_predict(Fp[:, [fn.index(n) for n in fm.model.rank_features]])
    else:
        Fp, fn, rs = np.zeros((0, 76)), [], np.zeros(0)
    keep = list(FF.nms(c, rs, fc.nms_dist, fc.nms_jacc, fc.max_out, fc.nms_overlap, fc.min_score, fc.min_keep))
    res = _output_residues(P, c, keep)
    ks = np.asarray(rs, float)[keep] if keep else np.zeros(0)
    kc = np.asarray(c.center, float)[keep].reshape(-1, 3) if keep else np.zeros((0, 3))
    in_v2 = np.zeros(len(keep), bool)
    in_v2[apply_rule("v2", ks, kc)] = True
    in_reg = np.zeros(len(keep), bool)
    in_reg[apply_rule(REGION_RULE, ks, kc)] = True
    members = [np.asarray(c.members(i), np.int64) for i in keep]
    indptr = np.zeros(len(keep) + 1, np.int64)
    indptr[1:] = np.cumsum([len(x) for x in members])
    mp = model_path()
    meta = {"adapter_version": ADAPTER_VERSION, "fast_adapter_version": FAST_ADAPTER_VERSION, "backend": "fast",
            "structure_path": None, "structure_sha256": None, "chains": None, "af_mode": bool(af_mode),
            "model_path": str(mp), "model_sha256": _sha256(str(mp)), "burrow_version": burrow_version(),
            "feature_cfg": json.loads(json.dumps(fm.model.meta["feature_cfg"])),
            "formation": dataclasses.asdict(fc), "region_rule": REGION_RULE, "n_candidates": len(c),
            "n_atoms": int(len(P.coords)), "n_points": int(len(ps.points)),
            "timings": {"pockets_s": time.perf_counter() - t0}}
    meta.update(extra_meta or {})
    z = np.zeros((0, 3), np.float32)
    return Featurized(
        key=key, points=np.ascontiguousarray(ps.points, np.float32), X=np.ascontiguousarray(ps.X, np.float32),
        vol=np.asarray(ps.vol, np.float32), is_metal=np.asarray(ps.is_metal, bool), point_score=score,
        feats=np.ascontiguousarray(ps.feats, np.float32), feature_names=names,
        atom_xyz=np.ascontiguousarray(P.coords, np.float32), atom_res=np.asarray(P.res_index, np.int32),
        atom_name=_STR(P.atom_name, 4), atom_element=_STR(P.element, 3), res_ids=_STR(P.residue_ids, 16),
        res_names=_res_names(P), het_xyz=z, het_element=np.zeros(0, "U3"), het_resname=np.zeros(0, "U5"),
        het_res=np.zeros(0, "U16"), pk_score=ks.astype(np.float64), pk_center=kc.astype(np.float64),
        pk_residues=np.asarray([" ".join(sort_residues(r)) for r in res] or np.zeros(0, "U1"), dtype=str),
        pk_indptr=indptr, pk_indices=np.concatenate(members) if members else np.zeros(0, np.int64),
        pk_desc=(Fp[keep] if keep else np.zeros((0, Fp.shape[1] if Fp.ndim == 2 else 76))).astype(np.float64),
        desc_names=list(fn), pk_in_v2=in_v2, pk_in_region=in_reg, meta=meta)


def featurize_fast_cpu(path, key: str, af_mode: bool = True, fm=None, chains=None) -> Featurized:
    """One structure through the fast Numba CPU path (no GPU)."""
    from pocketdetect.burrow.fast.pipeline import featurize
    fm = fm or fast_model()
    P, w, pld, npr = load_protein_af(path, key, af_mode, chains)
    ps = featurize(P, fm.cfg, w)
    fs = featurized_from_points(P, ps, None, fm, key, af_mode)
    fs.meta["n_res_pruned"] = npr
    return fs


__all__ = ["fast_model", "load_protein_af", "load_and_prep", "featurized_from_points", "featurize_fast_cpu",
           "FAST_ADAPTER_VERSION"]
