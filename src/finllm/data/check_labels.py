"""Compact per-document report: which financial statements were found, and where."""
import json, glob, sys
from itertools import groupby

root = sys.argv[1] if len(sys.argv) > 1 else "data/interim"
EXPECTED = ["Balance Sheet", "Statement of Profit and Loss", "Statement of Cash Flows"]

for f in sorted(glob.glob(f"{root}/*/*/pages_labeled.jsonl")):
    rows = [json.loads(l) for l in open(f, encoding="utf-8")]
    v = sum(r["printed_page_verified"] for r in rows)
    print(f"\n== {rows[0]['ticker']} {rows[0]['fy_label']}  pages={len(rows)}  verified_page_nums={v}")
    found = set()
    for k, g in groupby(rows, key=lambda r: r["section"] if r["section_source"] == "statement" else None):
        g = list(g)
        if k:
            print(f"   pdf {g[0]['page']}-{g[-1]['page']}  printed {g[0]['printed_page']}  {k}")
            found.add(k)
    for scope in ("Standalone", "Consolidated"):
        missing = [s for s in EXPECTED if not any(x.endswith(s) and x.startswith(scope) for x in found)]
        if missing: print(f"   MISSING ({scope}): {', '.join(missing)}")