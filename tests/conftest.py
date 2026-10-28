from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples"
DATA = Path(__file__).resolve().parent / "data"
PDB = EX / "pdb/1a28_A.pdb"                       # progesterone receptor LBD, holo crystal structure (ligand removed)
LIG = EX / "pdb/1a28_STR.pdb"                     # its progesterone (STR) ligand, heavy atoms
AF_CA2 = EX / "afdb/AF-P00918-F1-model_v6.cif.gz"  # carbonic anhydrase 2, AlphaFold model
AF_PR = EX / "afdb/AF-P06401-F1-model_v6.cif.gz"   # progesterone receptor, AlphaFold model


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: slower end-to-end test")


@pytest.fixture(scope="session")
def M():
    from pocketcompare import method
    return method.default()
