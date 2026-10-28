import json
import pathlib


def find_root():
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "configs" / "manifest.json").exists():
            return parent
    raise FileNotFoundError("configs/manifest.json not found in any parent folder")


ROOT = find_root()
MANIFEST = ROOT / "configs" / "manifest.json"
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def iter_reports():
    """Yield (ticker, company_dict, report_dict) for every report in the manifest."""
    for ticker, company in load_manifest()["companies"].items():
        for report in company["reports"]:
            yield ticker, company, report