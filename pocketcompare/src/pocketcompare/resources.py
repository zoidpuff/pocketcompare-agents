"""Location of the frozen method files (``configs/final_method.yaml`` and ``models/``).

Resolution order: ``$POCKETCOMPARE_DATA`` (a directory containing ``configs/`` and ``models/``), the copy inside an
installed wheel (``pocketcompare/_data``), the repository root (source checkout / editable install).
"""
from __future__ import annotations

import os
from pathlib import Path

PKG = Path(__file__).resolve().parent
CONFIG_REL = "configs/final_method.yaml"


def data_root() -> Path:
    env = os.environ.get("POCKETCOMPARE_DATA")
    cands = ([Path(env)] if env else []) + [PKG / "_data", PKG.parents[1]]
    for d in cands:
        if (d / CONFIG_REL).is_file():
            return d
    raise FileNotFoundError("pocketcompare method files not found (looked in: " + ", ".join(map(str, cands)) +
                            "). Install the package from the repository, or set POCKETCOMPARE_DATA to a "
                            "directory containing configs/ and models/.")


def default_config() -> Path:
    return data_root() / CONFIG_REL


__all__ = ["data_root", "default_config"]
