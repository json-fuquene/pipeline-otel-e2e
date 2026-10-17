from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .evidence import Evidence, analyze_directory
except ImportError:
    from evidence import Evidence, analyze_directory


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only offline evidence verification; no Docker or HTTP access")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    summary = analyze_directory(args.directory)
    if (args.directory / "summary.json").exists() or (args.directory / "summary.json").is_symlink():
        stored = Evidence(args.directory).json("summary.json", None)
        if stored != summary:
            summary["integrity"]["complete"] = False
            summary["integrity"]["errors"] = sorted(set(summary["integrity"]["errors"]) | {"stored_summary_mismatch"})
            summary["hypothesis"] = "inconclusa"
            summary["calculated_hypothesis"] = "inconclusa"
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0 if summary["integrity"]["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
