#!/usr/bin/env python
"""Rebuild all processed benchmark tables from data/raw (run the fetch_*.py scripts first).
Usage: python scripts/data/build_benchmarks.py && python scripts/data/check_benchmarks.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from pocketcompare.datasets import klifs, prospeccts, tough_c1, tough_m1, vertex  # noqa: E402

for mod in (prospeccts, tough_m1, vertex, tough_c1, klifs):
    print("building", mod.NAME)
    mod.build()
