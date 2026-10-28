"""Monte-Carlo error of the C1 bootstrap p-values: B = 20,000 with an independent seed (verifier code)."""
import json, sys
import numpy as np
sys.path.insert(0, "/cluster/project/beltrao/gmagnus/pocket_compare/results/verify")
from vlib import boot_paired
cid = sys.argv[1]; scr = sys.argv[2]
z = np.load(f"{scr}/tough_scores.npz")
a, b, D = {"C1a": ("FINAL_L", "B1_L", False), "C1b": ("FINAL_L", "B4_L", False), "C1-D": ("FINAL_D", "B1_D", True)}[cid]
sa, sb, y = z[a], z[b], z["y"]
m = np.isfinite(sa) & np.isfinite(sb) & (z["dset"] if D else True)
r = boot_paired(y[m], sa[m], sb[m], z["ua"][m], z["ub"][m], B=20000, seed=777)
bt = r.pop("boot")
r["p_by_2000_block"] = [float((1 + (bt[i:i+2000] <= 0).sum()) / 2001) for i in range(0, 20000, 2000)]
json.dump(r, open(f"/cluster/project/beltrao/gmagnus/pocket_compare/results/verify/v_tough_mc_{cid}.json", "w"), indent=1)
print(cid, r)
