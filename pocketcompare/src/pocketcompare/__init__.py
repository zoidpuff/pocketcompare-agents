"""pocketcompare: fast, ligand-free pocket fingerprints on BURROW pockets.

    from pocketcompare import method
    V, info = method.describe_all("structure.cif.gz")      # every pocket -> (n, 384) unit vectors
    S = method.similarity(V, V)                             # inner products (higher = more similar)
"""
__version__ = "1.0.0"
