import json
import sys
import time
from collections import Counter

import pymupdf

from common import INTERIM, RAW, iter_reports

BOLD_FLAG = 16  # bit set in a span's flags when the font is bold


def page_record(page, ticker, fy_label, page_no):
    d = page.get_text("dict")
    size_chars = Counter()  # font size -> number of characters at that size
    lines = []
    for block in d["blocks"]:
        if block["type"] != 0:  # 0 = text block, 1 = image block
            continue
        for line in block["lines"]:
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = "".join(s["text"] for s in line["spans"]).strip()
            for s in spans:
                size_chars[round(s["size"] * 2) / 2] += len(s["text"])
            lines.append({
                "text": text,
                "size": round(max(s["size"] for s in spans), 1),
                "bold": all((s["flags"] & BOLD_FLAG) or "bold" in s["font"].lower()
                            for s in spans),
                "y": round(line["bbox"][1]),
            })

    body = size_chars.most_common(1)[0][0] if size_chars else 0
    candidates = [l for l in lines
                  if 3 <= len(l["text"]) <= 120 and (l["size"] >= body * 1.2 or l["bold"])]
    text = page.get_text("text")
    return {
        "ticker": ticker,
        "fy_label": fy_label,
        "page": page_no,            # 1-indexed PDF page
        "text": text,
        "n_chars": len(text),
        "n_images": len(page.get_images()),
        "body_size": body,
        "candidates": candidates,   # possible headings, used in Step 3
    }


def main(force=False):
    for ticker, _company, r in iter_reports():
        pdf = RAW / r["file"]
        out = INTERIM / ticker / r["fy_label"] / "pages.jsonl"
        if out.exists() and not force:
            print(f"skip (exists): {ticker} {r['fy_label']}")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        doc = pymupdf.open(pdf)
        with out.open("w", encoding="utf-8") as f:
            for i, page in enumerate(doc, start=1):
                rec = page_record(page, ticker, r["fy_label"], i)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{ticker} {r['fy_label']}: {len(doc)} pages in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main(force="--force" in sys.argv)