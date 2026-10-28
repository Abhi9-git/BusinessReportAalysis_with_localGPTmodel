import json
import sys

from common import INTERIM

ticker, fy = sys.argv[1], sys.argv[2]
path = INTERIM / ticker / fy / "pages.jsonl"
pages = [json.loads(line) for line in path.open(encoding="utf-8")]

arg = " ".join(sys.argv[3:])
if arg.isdigit():                       # show one page
    p = pages[int(arg) - 1]
    print(f"--- {ticker} {fy} page {p['page']} (body font {p['body_size']}) ---")
    print(p["text"])
    print("\nheading candidates:")
    for c in p["candidates"]:
        print(f"  size={c['size']} bold={c['bold']}  {c['text']}")
else:                                   # search for a phrase
    for p in pages:
        if arg.lower() in p["text"].lower():
            print("page", p["page"])