#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def dim(s: str) -> str:
    return f"\033[2m{s}\033[0m" if _COLOR else s


def green(s: str) -> str:
    return f"\033[32m{s}\033[0m" if _COLOR else s


def bold(s: str) -> str:
    return f"\033[1m{s}\033[0m" if _COLOR else s


SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRY_FILE = SCRIPT_DIR / "registry.json"
FILES_DIR = SCRIPT_DIR / "files"

GAIN_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{4}\.[^.]+$", re.I)
GAIN_WIDTH = 16
GAIN_GROUP = 4

PHOTO_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif",
    ".bmp", ".tif", ".tiff", ".avif", ".jxl", ".raw", ".dng",
}
VIDEO_EXT = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv",
    ".flv", ".mpeg", ".mpg", ".3gp", ".mts", ".m2ts",
}
SKIP_NAMES = {"registry.json", "gain.py", ".ds_store", "thumbs.db", "desktop.ini"}


def format_gain(n: int) -> str:
    core = f"{n:0{GAIN_WIDTH}d}"
    return "-".join(core[i : i + GAIN_GROUP] for i in range(0, GAIN_WIDTH, GAIN_GROUP))


def file_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in PHOTO_EXT:
        return "photo"
    if ext in VIDEO_EXT:
        return "video"
    return "other"


def should_skip(path: Path) -> bool:
    return (
        path.name.startswith(".")
        or path.name.lower() in SKIP_NAMES
        or path.suffix.lower() == ".tmp"
    )


def collect_files(root: Path) -> list[Path]:
    files = [
        p
        for p in root.rglob("*")
        if p.is_file() and not should_skip(p) and not GAIN_RE.match(p.name)
    ]
    files.sort(key=lambda p: p.relative_to(root).as_posix().lower())
    return files


def load_next_id() -> int:
    if not REGISTRY_FILE.exists():
        return 1
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        return int(data["next_id"])
    except (ValueError, KeyError, OSError) as exc:
        raise SystemExit(f"Cannot read registry.json: {exc}")


def save_next_id(next_id: int) -> None:
    payload = {"next_id": next_id, "updated_at": datetime.now(timezone.utc).isoformat()}
    tmp = REGISTRY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(REGISTRY_FILE)


def run(dry_run: bool) -> int:
    FILES_DIR.mkdir(exist_ok=True)
    files = collect_files(FILES_DIR)

    if not files:
        print(dim("Nothing to rename."))
        return 0

    start_id = load_next_id()
    plan = [
        (src, src.with_name(f"{format_gain(start_id + offset)}{src.suffix.lower()}"))
        for offset, src in enumerate(files)
    ]

    existing = {p.stem for p in FILES_DIR.rglob("*") if p.is_file() and GAIN_RE.match(p.name)}
    clash = sorted(existing & {dst.stem for _, dst in plan})
    if clash:
        print(f"  {bold('Aborted.')} Name already exists: {clash[0]}", file=sys.stderr)
        print("  registry.json is out of sync with the files.", file=sys.stderr)
        return 1

    width = max(len(str(src.relative_to(FILES_DIR))) for src, _ in plan)
    for src, dst in plan:
        rel = str(src.relative_to(FILES_DIR)).ljust(width)
        print(f"  {dim(rel)}  {dim('->')}  {green(dst.name)}")
        if not dry_run:
            src.rename(dst)

    if not dry_run:
        save_next_id(start_id + len(plan))

    counts = {"photo": 0, "video": 0, "other": 0}
    for src, _ in plan:
        counts[file_kind(src)] += 1
    plurals = {"photo": "photos", "video": "videos", "other": "other"}
    kinds = ", ".join(
        f"{counts[k]} {k if counts[k] == 1 else plurals[k]}"
        for k in ("photo", "video", "other")
        if counts[k]
    )
    total = len(plan)
    files_word = "file" if total == 1 else "files"
    label = "Dry run:" if dry_run else "Renamed"

    print()
    print(f"  {bold(label)} {total} {files_word} ({kinds}).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Rename files in ./files to GAIN names.")
    parser.add_argument("-n", "--dry-run", action="store_true", help="preview only")
    args = parser.parse_args()
    return run(args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
