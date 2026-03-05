#!/usr/bin/env python3
"""Sync and verify canonical dashboard assets against vendored runtime assets."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import sys
import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

CANONICAL_DIR_NAMES: tuple[str, ...] = ("templates", "translations", "preferences")
CANONICAL_FILE_NAMES: tuple[str, ...] = ("dashboard_registry.json",)
TEMPLATE_SHARED_DIR_NAME = "shared"
_SHARED_TEMPLATE_MARKER_RE = re.compile(
    r"<<\s*template_shared\.([a-zA-Z0-9_./-]+)\s*>>"
)
_SHARED_TEMPLATE_MARKER_LINE_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)<<\s*template_shared\.(?P<fragment_id>[a-zA-Z0-9_./-]+)\s*>>\s*$"
)


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


def _discover_template_fragments(templates_root: Path) -> dict[str, str]:
    """Load shared template fragments keyed by marker id."""
    shared_root = templates_root / TEMPLATE_SHARED_DIR_NAME
    if not shared_root.exists():
        return {}

    fragments: dict[str, str] = {}
    for fragment_path in sorted(shared_root.rglob("*.yaml")):
        fragment_id = fragment_path.relative_to(shared_root).with_suffix("").as_posix()
        fragment_text = fragment_path.read_text(encoding="utf-8")
        fragments[fragment_id] = fragment_text
    return fragments


def _compose_template_text(
    template_text: str,
    fragments: dict[str, str],
    *,
    template_label: str,
) -> str:
    """Replace shared-fragment markers in template text recursively."""

    def resolve_fragment(fragment_id: str, stack: tuple[str, ...]) -> str:
        if fragment_id in stack:
            cycle = " -> ".join((*stack, fragment_id))
            raise ValueError(
                f"Circular template fragment reference in {template_label}: {cycle}"
            )
        if fragment_id not in fragments:
            raise ValueError(
                f"Missing template fragment '{fragment_id}' referenced by {template_label}"
            )

        fragment_source = fragments[fragment_id]

        def _replace_line(match: re.Match[str]) -> str:
            indent = match.group("indent")
            nested_id = match.group("fragment_id")
            resolved_nested = resolve_fragment(nested_id, (*stack, fragment_id))
            return textwrap.indent(resolved_nested, indent)

        def _replace_inline(match: re.Match[str]) -> str:
            nested_id = match.group(1)
            return resolve_fragment(nested_id, (*stack, fragment_id))

        composed_fragment = _SHARED_TEMPLATE_MARKER_LINE_RE.sub(
            _replace_line,
            fragment_source,
        )
        return _SHARED_TEMPLATE_MARKER_RE.sub(_replace_inline, composed_fragment)

    def _replace_root_line(match: re.Match[str]) -> str:
        indent = match.group("indent")
        fragment_id = match.group("fragment_id")
        resolved = resolve_fragment(fragment_id, ())
        return textwrap.indent(resolved, indent)

    def _replace_root_inline(match: re.Match[str]) -> str:
        fragment_id = match.group(1)
        return resolve_fragment(fragment_id, ())

    composed = _SHARED_TEMPLATE_MARKER_LINE_RE.sub(_replace_root_line, template_text)
    composed = _SHARED_TEMPLATE_MARKER_RE.sub(_replace_root_inline, composed)
    if _SHARED_TEMPLATE_MARKER_RE.search(composed):
        raise ValueError(
            f"Unresolved template_shared marker remains after compose in {template_label}"
        )
    return composed


def _build_composed_template_outputs(canonical_templates_root: Path) -> dict[Path, str]:
    """Build composed templates keyed by template-relative path."""
    if not canonical_templates_root.exists():
        raise FileNotFoundError(
            f"Missing templates directory: {canonical_templates_root}"
        )

    fragments = _discover_template_fragments(canonical_templates_root)
    outputs: dict[Path, str] = {}

    for template_path in sorted(canonical_templates_root.rglob("*.yaml")):
        relative_path = template_path.relative_to(canonical_templates_root)
        if relative_path.parts and relative_path.parts[0] == TEMPLATE_SHARED_DIR_NAME:
            continue
        raw_text = template_path.read_text(encoding="utf-8")
        composed_text = _compose_template_text(
            raw_text,
            fragments,
            template_label=f"templates/{relative_path.as_posix()}",
        )
        outputs[relative_path] = composed_text

    return outputs


def _hash_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


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
        src_dir = canonical_root / directory_name
        dst_dir = vendored_root / directory_name
        _copy_dir(src_dir, dst_dir)

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
        expected_paths = set(canonical_files)
        vendored_paths = set(vendored_files)

        missing_in_vendored = sorted(expected_paths - vendored_paths)
        extra_in_vendored = sorted(vendored_paths - expected_paths)

        for relative_path in missing_in_vendored:
            diffs.append(f"MISSING vendored/templates/{relative_path.as_posix()}")

        for relative_path in extra_in_vendored:
            diffs.append(f"EXTRA vendored/templates/{relative_path.as_posix()}")

        for relative_path in sorted(expected_paths & vendored_paths):
            vendored_file = vendored_dir / relative_path
            canonical_file = canonical_dir / relative_path
            if _hash_file(canonical_file) != _hash_file(vendored_file):
                diffs.append(f"MISMATCH templates/{relative_path.as_posix()}")

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
