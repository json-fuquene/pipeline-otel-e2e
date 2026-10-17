from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .common import write_json
    from .evidence import analyze_directory
except ImportError:
    from common import write_json
    from evidence import analyze_directory


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compute summary.json offline from a run's existing evidence")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    summary = analyze_directory(args.directory)
    if not args.directory.is_dir() or args.directory.is_symlink() or (args.directory / "summary.json").is_symlink():
        parser.exit(1, "Invalid evidence directory or output path.\n")
    try:
        write_json(args.directory / "summary.json", summary)
    except OSError:
        parser.exit(1, "Unable to write summary.json.\n")
    print("summary.json written; classification requires manual confirmation.")
    return 0 if summary["integrity"]["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
