import os

import pytest

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: simulation-heavy test (deselect with -m 'not slow')")


@pytest.fixture
def rng():
    import numpy as np

    from pocketcompare.seeds import SEEDS

    return np.random.default_rng(SEEDS[0])
