import json
import pathlib
from datetime import date

import pymupdf


def find_root():
    """Walk up from this file until a folder containing configs/manifest.json is found."""
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "configs" / "manifest.json").exists():
            return parent
    raise FileNotFoundError(
        "Could not find configs/manifest.json in any parent folder of " + str(here)
    )


ROOT = find_root()
MANIFEST = ROOT / "configs" / "manifest.json"
RAW = ROOT / "data" / "raw"
if not RAW.exists() and (ROOT / "DATA" / "RAW").exists():
    RAW = ROOT / "DATA" / "RAW"  # fallback if your folders are still uppercase


def check_metadata(r):
    problems = []
    start = date.fromisoformat(r["period_start"])
    end = date.fromisoformat(r["period_end"])
    days = (end - start).days + 1
    if not 360 <= days <= 371:
        problems.append(f"period is {days} days, expected about 365")
    if r["fy_label"] != f"FY{end.year}":
        problems.append(f"fy_label {r['fy_label']} does not match period_end {end}")
    if not r.get("reporting_unit"):
        problems.append("reporting_unit missing")
    fd = r.get("filing_date")
    if fd is None:
        problems.append("filing_date not filled yet")
    elif date.fromisoformat(fd) <= end:
        problems.append("filing_date is not after period_end")
    return problems


def audit_pdf(path):
    doc = pymupdf.open(path)
    n = len(doc)
    if n == 0:
        return {"pages": 0, "empty_pages": 0, "avg_chars_per_page": 0}
    chars = [len(page.get_text()) for page in doc]
    return {
        "pages": n,
        "empty_pages": sum(c < 50 for c in chars),
        "avg_chars_per_page": round(sum(chars) / n),
    }


def main():
    print("root:", ROOT)
    print("raw :", RAW)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    n_ok = n_missing = n_warn = 0
    for ticker, company in manifest["companies"].items():
        for r in company["reports"]:
            pdf = RAW / r["file"]
            print(f"\n{ticker} {r['fy_label']}")
            if not pdf.exists():
                print("  MISSING FILE:", pdf)
                n_missing += 1
                continue
            stats = audit_pdf(pdf)
            print("  pdf:", stats)
            if stats["pages"] and stats["empty_pages"] / stats["pages"] > 0.2:
                print("  WARN: over 20% of pages have almost no text (possibly scanned)")
                n_warn += 1
            for p in check_metadata(r):
                print("  WARN:", p)
                n_warn += 1
            n_ok += 1

    print(f"\nSummary: {n_ok} PDFs audited, {n_missing} missing, {n_warn} warnings")


if __name__ == "__main__":
    main()