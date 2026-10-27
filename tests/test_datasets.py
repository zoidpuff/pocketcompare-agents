"""Processed benchmark tables load and match the counts reported in
reports/data_benchmarks.md (which equal the original papers' numbers except
where noted). Skips if data/processed has not been built on this machine."""
import pytest

pd = pytest.importorskip("pandas")
from pocketcompare.datasets.common import PROCESSED_DIR  # noqa: E402

need = pytest.mark.skipif(not (PROCESSED_DIR / "prospeccts_pairs.parquet").exists(),
                          reason="benchmarks not built (scripts/data/fetch_*.py + build_benchmarks.py)")

# subset -> (n_pockets, n_pos, n_neg)
PROSPECCTS = {
    "P1": (326, 13430, 92846), "P1.2": (45, 241, 1784), "P2": (329, 7729, 100512),
    "P3": (1956, 13430, 67150), "P4": (1956, 13430, 67150), "P5": (80, 920, 5480),
    "P5.2": (100, 1320, 8680), "P6": (115, 19, 43), "P6.2": (115, 19, 43), "P7": (1151, 115, 56284),
}


def _load(name):
    return (pd.read_parquet(PROCESSED_DIR / f"{name}_pairs.parquet"),
            pd.read_parquet(PROCESSED_DIR / f"{name}_pockets.parquet"))


def _common_checks(pairs, pockets):
    assert pockets.pocket_id.is_unique
    assert pairs.pair_id.is_unique
    assert pairs.pocket_a.isin(pockets.pocket_id).all() and pairs.pocket_b.isin(pockets.pocket_id).all()
    assert set(pairs.label.unique()) <= {0, 1}


@need
def test_prospeccts():
    pairs, pockets = _load("prospeccts")
    _common_checks(pairs, pockets)
    for subset, (n, pos, neg) in PROSPECCTS.items():
        g = pairs[pairs.subset == subset]
        assert len(set(g.pocket_a) | set(g.pocket_b)) == n, subset
        assert (g.label == 1).sum() == pos, subset
        assert (g.label == 0).sum() == neg, subset
    for subset in ("P3", "P4"):  # paper's main 5-substitution decoy set
        g = pairs[(pairs.subset == subset) & (pairs.label == 0)]
        assert (g.decoy_nsub == 5).sum() == 13430
    assert len(pockets) == 6093 and not pockets.file_missing.any()
    assert (pockets.n_lig_residues == 1).all()


@need
def test_tough_m1():
    pairs, pockets = _load("tough_m1")
    _common_checks(pairs, pockets)
    assert len(pockets) == 7524
    assert (pairs.label == 1).sum() == 505116
    assert (pairs.label == 0).sum() == 556810
    assert not pockets.file_missing.any() and (pockets.n_pocket_residues > 0).all()


@need
def test_vertex():
    pairs, pockets = _load("vertex")
    _common_checks(pairs, pockets)
    assert len(pockets) == 6218 and pockets.pdb_id.nunique() == 6029
    assert (pairs.label == 1).sum() == 1461669  # DeeplyTough reports 1,461,668 (skips 1st data row)
    assert (pairs.label == 0).sum() == 102935
    prot = pairs.groupby("protein_pair").label.agg(["min", "max"])
    assert (prot["min"] == prot["max"]).all()
    assert (prot["min"] == 1).sum() == 6598 and (prot["max"] == 0).sum() == 379


@need
def test_tough_c1_and_klifs():
    c1 = pd.read_parquet(PROCESSED_DIR / "tough_c1_pockets.parquet")
    assert c1.groupby("subset").size().to_dict() == {"control": 1946, "heme": 596, "nucleotide": 1553, "steroid": 69}
    kl = pd.read_parquet(PROCESSED_DIR / "klifs_pockets.parquet")
    assert len(kl) > 10000 and kl.pocket_id.is_unique
    # KLIFS API snapshot 2026-10-27: 14,917 structures, 112 with pocket string != 85 chars
    assert (kl.pocket_def.str.len() == 85).mean() > 0.99


@pytest.mark.skipif(not (PROCESSED_DIR / "tough_m1_pockets.parquet").exists(), reason="pocket table not built")
def test_tough_m1_pocket_chain_matches_structure_file():
    """pocket_def uses the chain letter of the structure file (was hard-coded 'A:' before 2026-10-27)."""
    from pocketcompare.datasets.common import PROJECT_ROOT
    k = pd.read_parquet(PROCESSED_DIR / "tough_m1_pockets.parquet")
    assert len(k) == 7524 and (k.structure_chain != "A").sum() == 3191
    assert (k.pocket_def.str.split(":").str[0] == k.structure_chain).all()
    assert (k.structure_chain == k.name.str[4]).all()
    for r in k.sample(50, random_state=0).itertuples():
        res = {(l[21], l[22:27].strip()) for l in open(PROJECT_ROOT / r.structure_path) if l.startswith("ATOM")}
        ch, nums = r.pocket_def.split(":")
        assert all((ch, n) in res for n in nums.split(","))
    assert not (PROCESSED_DIR / "tough_m1_pairs.parquet").exists(), "sealed pair table must not be rebuilt"
