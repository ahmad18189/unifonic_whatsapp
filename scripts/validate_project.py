"""Static checks runnable without a Frappe bench; not a substitute for integration tests."""
from pathlib import Path
import json
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "unifonic_whatsapp"

def main():
    failed = []
    python_files = list(PACKAGE.rglob("*.py"))
    for path in python_files:
        try: ast.parse(path.read_text(encoding="utf8"), filename=str(path))
        except Exception as e: failed.append(f"syntax: {path}: {e}")
    doctypes = list((PACKAGE / "unifonic_whatsapp" / "doctype").glob("*/*.json"))
    if len(doctypes) != 7: failed.append(f"expected 7 DocTypes, got {len(doctypes)}")
    for path in doctypes:
        try:
            d = json.loads(path.read_text(encoding="utf8"))
            fields = [f["fieldname"] for f in d["fields"]]
            if len(fields) != len(set(fields)):
                failed.append(f"duplicate fieldnames: {path}")
            if d["field_order"] != fields:
                failed.append(f"field_order mismatch: {path}")
            if not d.get("permissions"):
                failed.append(f"missing permission definitions: {path}")
        except Exception as e: failed.append(f"bad doctype JSON: {path}: {e}")
    for path in (ROOT / "examples").glob("*.json"):
        try: json.loads(path.read_text(encoding="utf8"))
        except Exception as e: failed.append(f"invalid example JSON {path}: {e}")
    for path in (ROOT / "AGENTS.md", ROOT / "docs/SRS.md", ROOT / "docs/API_CONTRACT.md",
                 ROOT / "frontend/src/Inbox.vue", ROOT / "frontend/src/App.vue"):
        if not path.is_file(): failed.append(f"missing file: {path}")
    print(f"Checked {len(python_files)} Python files, {len(doctypes)} DocTypes, examples and instructions")
    for failure in failed: print(f"FAIL: {failure}")
    if failed: sys.exit(1)
    print("Static validation: PASS (Frappe + provider integration not executed)")

if __name__ == "__main__": main()
