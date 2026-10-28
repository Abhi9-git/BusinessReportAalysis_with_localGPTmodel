"""Step 3 (v2): label every page with section, scope and printed page number.
Usage: python label_sections.py <pages.jsonl> [out.jsonl]
Adds: printed_page, printed_page_verified, header, section, section_source, scope, statement
"""
import json, re, sys
from collections import Counter
from pathlib import Path

WS = re.compile(r"[\s\u2003\u00a0\u200b]+")
def clean(s): return WS.sub(" ", s).strip()
def lines_of(text): return [clean(l) for l in text.split("\n") if clean(l)]

# ---------- printed page number: vote for the document's page offset ----------
def edge_numbers(r):
    ls = lines_of(r["text"]); edge = ls[:3] + ls[-3:]
    nums = set()
    for l in edge:
        if len(l) > 70: continue
        for tok in (l.split()[0], l.split()[-1]):
            if tok.isdigit() and 1 <= int(tok) <= 999: nums.add(int(tok))
    for c in r["candidates"]:
        t = clean(c["text"])
        if t.isdigit() and 1 <= int(t) <= 999: nums.add(int(t))
    return nums

def assign_page_numbers(rows):
    votes = Counter()
    for r in rows:
        r["_nums"] = edge_numbers(r)
        for n in r["_nums"]: votes[r["page"] - n] += 1
    offset, top = (votes.most_common(1)[0] if votes else (0, 0))
    ok = top >= 0.3 * len(rows)            # offset must be backed by many pages
    for r in rows:
        if ok and r["page"] - offset >= 1:
            r["printed_page"] = r["page"] - offset
            r["printed_page_verified"] = (r["page"] - offset) in r["_nums"]
        else:
            r["printed_page"], r["printed_page_verified"] = r["page"], False
        del r["_nums"]

# ---------- running header (fallback signal) ----------
def header_of(r):
    hs = [clean(c["text"]) for c in r["candidates"] if c["y"] < 70]
    hs = [h for h in hs if h and not h.isdigit()]
    return re.sub(r"\s*\(Contd\.?\)\s*$", "", hs[0], flags=re.I) if hs else None

def divider_title(r):
    t = clean(r["text"])
    if r["n_chars"] < 80 and len(t) > 8 and t.upper() == t and re.search("[A-Z]{4}", t):
        return t.title()
    return None

# ---------- financial statements: title first, content cues for continuation ----------
STATEMENTS = {
  "Balance Sheet": (r"^(consolidated |standalone )?balance sheets?\b",
                    r"total (equity and liabilities|assets)|non-?current assets|equity and liabilities"),
  "Statement of Profit and Loss": (r"^(consolidated |standalone )?(statements? of profit (and|or) loss|profit and loss (account|statement)|statements? of (comprehensive )?income)\b",
                    r"earnings per|profit before tax|total comprehensive income|total expenses"),
  "Statement of Cash Flows": (r"^(consolidated |standalone )?(statements? of cash flows?|cash flows? statement)\b",
                    r"(investing|financing|operating) activities"),
  "Statement of Changes in Equity": (r"^(consolidated |standalone )?statements? of changes in equity\b",
                    r"reserves and surplus|balance as at|changes in equity"),
}
# major sections that start once (title appears one time, so never frequency-filter them)
MAJOR = [
  (r"independent auditor.?s report", "Independent Auditor’s Report"),
  (r"^notes to (the )?(consolidated |standalone )?financial statements|^notes forming part of", "Notes to Financial Statements"),
  (r"^board.?s report|^directors.? report", "Board’s Report"),
  (r"^management discussion", "Management Discussion and Analysis"),
  (r"^(report on )?corporate governance", "Corporate Governance"),
  (r"^business responsibility", "Business Responsibility & Sustainability Report"),
]
def scope_in(text):
    t = text.lower()
    c, s = t.count("consolidated"), t.count("standalone")
    return "Consolidated" if c > s else "Standalone" if s > c else None

def numeric_density(text): return len(re.findall(r"\(?\d[\d,]*\.\d+\)?|\d{1,3}(?:,\d{2,3})+", text))

# title-less statements (title is a graphic): match the table's own shape
SHAPES = [
  ("Balance Sheet", r"particulars\s+notes?\s+as at\s+31\.03\.\d{4}.*?assets"),
  ("Statement of Profit and Loss", r"particulars\s+notes?\s+year\s+\d{4}-\d{2}.*?revenue from operations"),
]

def detect_statement(r, prev_stmt, run):
    ls = lines_of(r["text"])[:8]
    dense = numeric_density(r["text"]) >= 15
    colhdr = (any(re.fullmatch(r"balance sheet", l, re.I) for l in ls) and
              any(re.match(r"profit", l, re.I) for l in ls))   # a notes table's column labels
    notes_page = any(re.match(r"notes to (the )?", l, re.I) for l in ls[:2])
    if dense and not colhdr and not notes_page:
        for l in ls[:6]:
            if len(l) > 90: continue
            for name, (title, _) in STATEMENTS.items():
                if re.search(title, l, re.I): return name, scope_in(l)
        flat = clean(r["text"]).lower()[:700]
        for name, pat in SHAPES:
            if re.search(pat, flat): return name, None
    if prev_stmt and run < 3 and dense:             # continuation page: content cues, max 3 pages
        if re.search(STATEMENTS[prev_stmt][1], r["text"], re.I): return prev_stmt, None
    return None, None

def label(rows):
    hdr_count = Counter(header_of(r) for r in rows if header_of(r))
    current, src, scope = "Front matter", "default", None
    prev_stmt, run = None, 0
    for r in rows:
        h, d = header_of(r), divider_title(r)
        r["header"] = h
        stmt, sc = detect_statement(r, prev_stmt, run)
        if stmt:
            run = run + 1 if stmt == prev_stmt else 0
            prev_stmt = stmt
            scope = sc or scope
            r["section"] = f"{scope} {stmt}" if scope else stmt
            r["section_source"], r["statement"] = "statement", stmt
        else:
            prev_stmt, run = None, 0
            head = " ".join(lines_of(r["text"])[:6]).lower()
            hit = next((n for p, n in MAJOR if re.search(p, head)), None)
            if d:                                  current, src = d, "divider"
            elif hit:                              current, src = hit, "major_title"
            elif h and hdr_count[h] >= 3:          current, src = h, "running_header"
            scope = scope_in(current) or scope
            if "auditor" in current.lower():       # auditor's report text says which FS it covers
                scope = scope_in(" ".join(lines_of(r["text"])[:25])) or scope
            r["section"], r["section_source"], r["statement"] = current, src, None
        r["scope"] = scope

def process(src, out):
    allrows = [json.loads(l) for l in Path(src).read_text(encoding="utf-8").splitlines()]
    rows = sorted(allrows, key=lambda r: r["page"])
    assign_page_numbers(rows); label(rows)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote", out)

if __name__ == "__main__":
    src = Path(sys.argv[1])
    process(src, sys.argv[2] if len(sys.argv) > 2 else src.with_name("pages_labeled.jsonl"))