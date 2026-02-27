#!/usr/bin/env python3
"""Sync and verify canonical dashboard assets against vendored runtime assets."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

CANONICAL_DIR_NAMES: tuple[str, ...] = ("templates", "translations", "preferences")
CANONICAL_FILE_NAMES: tuple[str, ...] = ("dashboard_registry.json",)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_canonical_root() -> Path:
    return _repo_root().parent / "choreops-dashboards"


def _default_vendored_root() -> Path:
    return _repo_root() / "custom_components" / "choreops" / "dashboards"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_relative_files(root: Path) -> list[Path]:
    return sorted(
        file_path.relative_to(root)
        for file_path in root.rglob("*")
        if file_path.is_file()
    )


def _copy_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _ensure_paths_exist(paths: Iterable[Path], descriptor: str) -> None:
    missing_paths = [str(path) for path in paths if not path.exists()]
    if missing_paths:
        missing_text = ", ".join(sorted(missing_paths))
        raise FileNotFoundError(f"Missing {descriptor}: {missing_text}")


def _write_stdout(message: str) -> None:
    sys.stdout.write(f"{message}\n")


def _write_stderr(message: str) -> None:
    sys.stderr.write(f"{message}\n")


def sync_assets(canonical_root: Path, vendored_root: Path) -> None:
    _ensure_paths_exist((canonical_root,), "canonical root")
    vendored_root.mkdir(parents=True, exist_ok=True)

    for directory_name in CANONICAL_DIR_NAMES:
        _copy_dir(canonical_root / directory_name, vendored_root / directory_name)

    for file_name in CANONICAL_FILE_NAMES:
        shutil.copy2(canonical_root / file_name, vendored_root / file_name)


def parity_diff(canonical_root: Path, vendored_root: Path) -> list[str]:
    diffs: list[str] = []

    for directory_name in CANONICAL_DIR_NAMES:
        canonical_dir = canonical_root / directory_name
        vendored_dir = vendored_root / directory_name
        _ensure_paths_exist(
            (canonical_dir, vendored_dir), f"{directory_name} directory"
        )

        canonical_files = _iter_relative_files(canonical_dir)
        vendored_files = _iter_relative_files(vendored_dir)

        canonical_set = set(canonical_files)
        vendored_set = set(vendored_files)

        missing_in_vendored = sorted(canonical_set - vendored_set)
        extra_in_vendored = sorted(vendored_set - canonical_set)

        for relative_path in missing_in_vendored:
            diffs.append(
                f"MISSING vendored/{directory_name}/{relative_path.as_posix()}"
            )

        for relative_path in extra_in_vendored:
            diffs.append(f"EXTRA vendored/{directory_name}/{relative_path.as_posix()}")

        for relative_path in sorted(canonical_set & vendored_set):
            canonical_file = canonical_dir / relative_path
            vendored_file = vendored_dir / relative_path
            if _hash_file(canonical_file) != _hash_file(vendored_file):
                diffs.append(f"MISMATCH {directory_name}/{relative_path.as_posix()}")

    for file_name in CANONICAL_FILE_NAMES:
        canonical_file = canonical_root / file_name
        vendored_file = vendored_root / file_name
        _ensure_paths_exist((canonical_file, vendored_file), file_name)
        if _hash_file(canonical_file) != _hash_file(vendored_file):
            diffs.append(f"MISMATCH {file_name}")

    return diffs


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Sync canonical ChoreOps dashboard assets into vendored runtime assets.",
    )
    parser.add_argument(
        "--canonical-root",
        type=Path,
        default=_default_canonical_root(),
        help="Path to canonical dashboard repository root",
    )
    parser.add_argument(
        "--vendored-root",
        type=Path,
        default=_default_vendored_root(),
        help="Path to vendored dashboard assets root",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check parity and fail if drift exists",
    )
    return parser.parse_args()


def main() -> int:
    """Run sync or parity check command."""
    args = parse_args()
    canonical_root = args.canonical_root.resolve()
    vendored_root = args.vendored_root.resolve()

    if args.check:
        try:
            diffs = parity_diff(canonical_root, vendored_root)
        except FileNotFoundError as error:
            _write_stderr(f"Path validation failed: {error}")
            return 2

        if diffs:
            _write_stderr("Dashboard asset parity check failed:")
            for diff in diffs:
                _write_stderr(f" - {diff}")
            _write_stderr(
                "Run utils/sync_dashboard_assets.py to synchronize vendored assets."
            )
            return 1

        _write_stdout("Dashboard asset parity check passed")
        return 0

    try:
        sync_assets(canonical_root, vendored_root)
        diffs = parity_diff(canonical_root, vendored_root)
    except FileNotFoundError as error:
        _write_stderr(f"Path validation failed: {error}")
        return 2

    if diffs:
        _write_stderr("Dashboard asset sync completed but parity check failed:")
        for diff in diffs:
            _write_stderr(f" - {diff}")
        return 1

    _write_stdout("Dashboard asset sync completed and parity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
