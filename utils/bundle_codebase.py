# ruff: noqa: INP001
import argparse
from datetime import date
import os
from pathlib import Path

# Get the ISO 8601 formatted date (e.g., "2026-03-20")
CURRENT_DATE = date.today().isoformat()

# Dynamically find paths based on where this script lives
SCRIPT_DIR = Path(__file__).resolve().parent  # This is always choreops/utils/
WORKSPACE_ROOT = (SCRIPT_DIR / ".." / "..").resolve()  # This is the workspace root
CHOREOPS_REPO_ROOT = (SCRIPT_DIR / "..").resolve()

BACKEND_TRANSLATION_DIRS = (
    Path("choreops/custom_components/choreops/translations"),
    Path("choreops/custom_components/choreops/translations_custom"),
)

BACKEND_TRANSLATION_SOURCE_DIRS = (
    CHOREOPS_REPO_ROOT / "custom_components/choreops/translations",
    CHOREOPS_REPO_ROOT / "custom_components/choreops/translations_custom",
)


def _should_skip_dir(
    root: Path, dir_name: str, excluded_dirs: tuple[Path, ...]
) -> bool:
    """Return whether a directory should be skipped during os.walk."""
    if dir_name.startswith(".") or dir_name in ("__pycache__", "exports"):
        return True

    candidate = (root / dir_name).relative_to(WORKSPACE_ROOT)
    return any(
        candidate == excluded_dir or excluded_dir in candidate.parents
        for excluded_dir in excluded_dirs
    )


def _write_file_to_bundle(outfile, file_path: Path) -> None:
    """Write one file into the bundle output with a path header."""
    rel_path = file_path.relative_to(WORKSPACE_ROOT)

    outfile.write(f"\n\n{'=' * 80}\n")
    outfile.write(f"FILE PATH: {rel_path}\n")
    outfile.write(f"{'=' * 80}\n\n")

    try:
        with file_path.open(encoding="utf-8") as infile:
            outfile.write(infile.read())
    except Exception as err:
        outfile.write(f"[Error reading file: {err}]\n")
        print(f"❌ Skipped {rel_path} due to read error.")  # noqa: T201


def _resolve_backend_translation_files(language_selector: str) -> list[Path]:
    """Return backend translation files for one language or for all languages."""
    translation_files: list[Path] = []

    for translation_dir in BACKEND_TRANSLATION_SOURCE_DIRS:
        if not translation_dir.exists():
            continue

        for file_path in sorted(translation_dir.glob("*.json")):
            stem = file_path.stem
            language_code = stem.split("_", maxsplit=1)[0]

            if language_selector not in ("all", language_code):
                continue

            translation_files.append(file_path)

    return translation_files


def bundle_backend_translations(language_selector: str) -> None:
    """Bundle backend translation files into a dedicated export."""
    translation_files = _resolve_backend_translation_files(language_selector)

    if not translation_files:
        print(  # noqa: T201
            "⚠️ Warning: no backend translation files matched the requested language selector."
        )
        return

    export_dir = SCRIPT_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    dated_filename = (
        f"gem_choreops_backend_translations_{language_selector}_{CURRENT_DATE}.txt"
    )
    output_path = export_dir / dated_filename

    print(  # noqa: T201
        "📦 Bundling backend translations into "
        f"'choreops/utils/exports/{dated_filename}' using selector '{language_selector}'..."
    )

    with output_path.open("w", encoding="utf-8") as outfile:
        for file_path in translation_files:
            _write_file_to_bundle(outfile, file_path)


def parse_args() -> argparse.Namespace:
    """Parse command-line options for bundle export behavior."""
    parser = argparse.ArgumentParser(
        description="Bundle ChoreOps codebase exports for external import tools."
    )
    parser.add_argument(
        "--backend-translations",
        default="en",
        metavar="LANG",
        help=(
            "Backend translation export selector: default 'en', use 'all' for every "
            "language, or a specific two-letter code such as 'fr' or 'de'."
        ),
    )
    return parser.parse_args()


def bundle_for_gem(
    source_folder_name: str,
    output_filename: str,
    allowed_extensions: tuple[str, ...],
    *,
    excluded_dirs: tuple[Path, ...] = (),
) -> None:
    """Walks a directory and concatenates files into a single LLM-friendly document."""
    source_dir = WORKSPACE_ROOT / source_folder_name

    # Check if the repo actually exists in the workspace
    if not source_dir.exists():
        print(f"⚠️ Warning: '{source_folder_name}' not found in workspace. Skipping.")  # noqa: T201
        return

    # Safely split the filename to inject the ISO date (e.g., name_2026-03-20.txt)
    out_path_obj = Path(output_filename)
    dated_filename = f"{out_path_obj.stem}_{CURRENT_DATE}{out_path_obj.suffix}"

    # Target the centralized choreops/utils/exports/ folder
    export_dir = SCRIPT_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    output_path = export_dir / dated_filename

    print(  # noqa: T201
        f"📦 Bundling '{source_folder_name}' into 'choreops/utils/exports/{dated_filename}'..."
    )

    with output_path.open("w", encoding="utf-8") as outfile:
        for root_str, dirs, files in os.walk(source_dir):
            root = Path(root_str)

            # Skip hidden dirs, Python caches, and our new central 'exports' directory!
            dirs[:] = [d for d in dirs if not _should_skip_dir(root, d, excluded_dirs)]

            for file in files:
                if file.endswith(allowed_extensions):
                    file_path = root / file
                    rel_path = file_path.relative_to(WORKSPACE_ROOT)

                    if any(
                        rel_path == excluded_dir or excluded_dir in rel_path.parents
                        for excluded_dir in excluded_dirs
                    ):
                        continue

                    _write_file_to_bundle(outfile, file_path)


# --- EXECUTION ---
if __name__ == "__main__":
    args = parse_args()
    backend_translation_selector = args.backend_translations.strip().lower()

    if backend_translation_selector != "all" and len(backend_translation_selector) != 2:
        msg = (
            "--backend-translations must be 'all' or a specific two-letter "
            "language code such as 'en', 'fr', or 'de'."
        )
        raise SystemExit(msg)

    print(f"🚀 Starting Knowledge Base Bundler in Workspace: {WORKSPACE_ROOT}\n")  # noqa: T201

    # 1. Bundle the Core Integration
    bundle_for_gem(
        source_folder_name="choreops",
        output_filename="gem_choreops_backend.txt",
        allowed_extensions=(".py", ".yaml", ".json"),
        excluded_dirs=BACKEND_TRANSLATION_DIRS,
    )

    # 1b. Bundle backend translations separately
    bundle_backend_translations(backend_translation_selector)

    # 2. Bundle the Dashboards
    bundle_for_gem(
        source_folder_name="choreops-dashboards",
        output_filename="gem_choreops_dashboards.txt",
        allowed_extensions=(".yaml", ".js", ".json", ".html"),
    )

    # 3. Bundle the Wiki
    bundle_for_gem(
        source_folder_name="choreops-wiki",
        output_filename="gem_choreops_wiki.txt",
        allowed_extensions=(".md",),
    )

    print("\n✅ Bundling complete! Check the 'choreops/utils/exports/' folder.")  # noqa: T201
