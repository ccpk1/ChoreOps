# ruff: noqa: INP001
from datetime import date
import os
from pathlib import Path

# Get the ISO 8601 formatted date (e.g., "2026-03-20")
CURRENT_DATE = date.today().isoformat()

# Dynamically find paths based on where this script lives
SCRIPT_DIR = Path(__file__).resolve().parent  # This is always choreops/utils/
WORKSPACE_ROOT = (SCRIPT_DIR / ".." / "..").resolve()  # This is the workspace root


def bundle_for_gem(
    source_folder_name: str, output_filename: str, allowed_extensions: tuple[str, ...]
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
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in ("__pycache__", "exports")
            ]

            for file in files:
                if file.endswith(allowed_extensions):
                    file_path = root / file
                    rel_path = file_path.relative_to(WORKSPACE_ROOT)

                    outfile.write(f"\n\n{'=' * 80}\n")
                    outfile.write(f"FILE PATH: {rel_path}\n")
                    outfile.write(f"{'=' * 80}\n\n")

                    try:
                        with file_path.open(encoding="utf-8") as infile:
                            outfile.write(infile.read())
                    except Exception as e:
                        outfile.write(f"[Error reading file: {e}]\n")
                        print(f"❌ Skipped {rel_path} due to read error.")  # noqa: T201


# --- EXECUTION ---
if __name__ == "__main__":
    print(f"🚀 Starting Knowledge Base Bundler in Workspace: {WORKSPACE_ROOT}\n")  # noqa: T201

    # 1. Bundle the Core Integration
    bundle_for_gem(
        source_folder_name="choreops",
        output_filename="gem_choreops_backend.txt",
        allowed_extensions=(".py", ".yaml", ".json"),
    )

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
