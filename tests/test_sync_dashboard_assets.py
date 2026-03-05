"""Tests for dashboard asset sync copy/parity behavior."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType


def _load_sync_module() -> ModuleType:
    """Load sync_dashboard_assets module from file path."""
    module_path = Path("utils/sync_dashboard_assets.py")
    spec = spec_from_file_location("sync_dashboard_assets", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sync_copies_templates_and_shared_directory_byte_identical(
    tmp_path: Path,
) -> None:
    """Sync copies templates/shared files byte-identical from canonical to vendored."""
    sync_module = _load_sync_module()

    canonical_root = tmp_path / "choreops-dashboards"
    vendored_root = (
        tmp_path / "choreops" / "custom_components" / "choreops" / "dashboards"
    )

    templates_root = canonical_root / "templates"
    shared_root = templates_root / "shared" / "rows" / "chore"
    translations_root = canonical_root / "translations"
    preferences_root = canonical_root / "preferences"

    shared_root.mkdir(parents=True, exist_ok=True)
    translations_root.mkdir(parents=True, exist_ok=True)
    preferences_root.mkdir(parents=True, exist_ok=True)

    (templates_root / "user-minimal-v1.yaml").write_text(
        "start\n<< template_shared.rows/chore/action_v1 >>\nend\n",
        encoding="utf-8",
    )
    (shared_root / "action_v1.yaml").write_text(
        "nested-row-content\n", encoding="utf-8"
    )
    (translations_root / "en_dashboard.json").write_text("{}", encoding="utf-8")
    (preferences_root / "user-minimal-v1.md").write_text("# Prefs\n", encoding="utf-8")
    (canonical_root / "dashboard_registry.json").write_text(
        '{"schema_version": 1, "templates": []}', encoding="utf-8"
    )

    sync_module.sync_assets(canonical_root, vendored_root)

    assert (vendored_root / "templates" / "user-minimal-v1.yaml").read_text(
        encoding="utf-8"
    ) == "start\n<< template_shared.rows/chore/action_v1 >>\nend\n"
    assert (
        vendored_root / "templates" / "shared" / "rows" / "chore" / "action_v1.yaml"
    ).read_text(encoding="utf-8") == "nested-row-content\n"

    assert sync_module.parity_diff(canonical_root, vendored_root) == []


def test_sync_preserves_template_source_with_shared_marker_line(tmp_path: Path) -> None:
    """Sync preserves shared marker lines in canonical template source."""
    sync_module = _load_sync_module()

    canonical_root = tmp_path / "choreops-dashboards"
    vendored_root = (
        tmp_path / "choreops" / "custom_components" / "choreops" / "dashboards"
    )

    templates_root = canonical_root / "templates"
    shared_root = templates_root / "shared"
    translations_root = canonical_root / "translations"
    preferences_root = canonical_root / "preferences"

    shared_root.mkdir(parents=True, exist_ok=True)
    translations_root.mkdir(parents=True, exist_ok=True)
    preferences_root.mkdir(parents=True, exist_ok=True)

    (templates_root / "user-minimal-v1.yaml").write_text(
        "button_card_templates:\n  << template_shared.row_v1 >>\nafter: true\n",
        encoding="utf-8",
    )
    (shared_root / "row_v1.yaml").write_text(
        "choreops_chore_row_v1:\n  key: value\n",
        encoding="utf-8",
    )
    (translations_root / "en_dashboard.json").write_text("{}", encoding="utf-8")
    (preferences_root / "user-minimal-v1.md").write_text("# Prefs\n", encoding="utf-8")
    (canonical_root / "dashboard_registry.json").write_text(
        '{"schema_version": 1, "templates": []}', encoding="utf-8"
    )

    sync_module.sync_assets(canonical_root, vendored_root)

    assert (vendored_root / "templates" / "user-minimal-v1.yaml").read_text(
        encoding="utf-8"
    ) == "button_card_templates:\n  << template_shared.row_v1 >>\nafter: true\n"
    assert sync_module.parity_diff(canonical_root, vendored_root) == []


def test_sync_allows_unresolved_shared_marker_in_template_source(
    tmp_path: Path,
) -> None:
    """Sync preserves template source markers without requiring fragment presence."""
    sync_module = _load_sync_module()

    canonical_root = tmp_path / "choreops-dashboards"
    vendored_root = (
        tmp_path / "choreops" / "custom_components" / "choreops" / "dashboards"
    )

    templates_root = canonical_root / "templates"
    translations_root = canonical_root / "translations"
    preferences_root = canonical_root / "preferences"

    templates_root.mkdir(parents=True, exist_ok=True)
    translations_root.mkdir(parents=True, exist_ok=True)
    preferences_root.mkdir(parents=True, exist_ok=True)

    (templates_root / "user-minimal-v1.yaml").write_text(
        "start\n<< template_shared.missing_fragment_v1 >>\nend\n",
        encoding="utf-8",
    )
    (translations_root / "en_dashboard.json").write_text("{}", encoding="utf-8")
    (preferences_root / "user-minimal-v1.md").write_text("# Prefs\n", encoding="utf-8")
    (canonical_root / "dashboard_registry.json").write_text(
        '{"schema_version": 1, "templates": []}', encoding="utf-8"
    )

    sync_module.sync_assets(canonical_root, vendored_root)

    assert (vendored_root / "templates" / "user-minimal-v1.yaml").read_text(
        encoding="utf-8"
    ) == "start\n<< template_shared.missing_fragment_v1 >>\nend\n"
