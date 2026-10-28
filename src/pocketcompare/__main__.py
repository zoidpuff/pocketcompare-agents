"""``python -m pocketcompare`` == the ``pocketcompare`` console script (``pocketcompare.cli``)."""
import sys

from .cli import main

sys.exit(main())
