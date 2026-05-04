#!/usr/bin/env python3
"""Generate dense ChoreOps test scenarios for stress and manual validation."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Final

import yaml

OUTPUT_DIR: Final = Path("/workspaces/choreops/tests/scenarios")
DEFAULT_COUNTS: Final[tuple[int, ...]] = (40, 50, 60, 70, 80, 90, 100)

ASSIGNEES: Final[tuple[dict[str, str], ...]] = (
    {"name": "Zoë", "ha_user": "assignee1", "dashboard_language": "en"},
    {"name": "Max!", "ha_user": "assignee2", "dashboard_language": "en"},
    {"name": "Lila", "ha_user": "assignee3", "dashboard_language": "en"},
)

APPROVERS: Final[tuple[dict[str, str], ...]] = (
    {"name": "Môm Astrid Stårblüm", "ha_user": "approver1"},
    {"name": "Dad Leo Stårblüm", "ha_user": "approver2"},
)

LABELS: Final[tuple[str, ...]] = (
    "Kitchen",
    "Bedroom",
    "Bathroom",
    "Laundry",
    "School",
    "Outdoor",
)

ICONS: Final[tuple[str, ...]] = (
    "mdi:broom",
    "mdi:spray-bottle",
    "mdi:trash-can-outline",
    "mdi:book-open-page-variant",
    "mdi:washing-machine",
    "mdi:shovel",
)


class _ScenarioDumper(yaml.SafeDumper):
    """YAML dumper that keeps generated scenarios fully expanded."""

    def ignore_aliases(self, data: object) -> bool:
        """Disable anchors/aliases for readability of generated fixtures."""
        return True


def _build_chore_name(assignee_name: str, chore_index: int) -> str:
    """Build a stable unique chore name for generated scenarios."""
    return f"{assignee_name} Dense Chore {chore_index:03d}"


def build_dense_scenario(chores_per_assignee: int) -> dict[str, object]:
    """Build a dense scenario with the standard Stårblüm family.

    Each assignee receives the same number of independent chores so the
    resulting dashboard helper size is directly comparable per user.
    """
    assignee_names = [assignee["name"] for assignee in ASSIGNEES]
    chores: list[dict[str, object]] = []

    for assignee_index, assignee in enumerate(ASSIGNEES):
        assignee_name = assignee["name"]
        for chore_index in range(1, chores_per_assignee + 1):
            label_index = (chore_index - 1) % len(LABELS)
            secondary_label_index = (label_index + assignee_index + 1) % len(LABELS)
            icon = ICONS[(chore_index - 1) % len(ICONS)]
            points = float(5 + ((chore_index - 1) % 6) * 5)

            chores.append(
                {
                    "name": _build_chore_name(assignee_name, chore_index),
                    "assigned_to": [assignee_name],
                    "points": points,
                    "icon": icon,
                    "description": (
                        f"Generated dense dashboard chore {chore_index} for "
                        f"{assignee_name}"
                    ),
                    "completion_criteria": "independent",
                    "recurring_frequency": "daily",
                    "auto_approve": True,
                    "show_on_calendar": False,
                    "labels": [
                        LABELS[label_index],
                        LABELS[secondary_label_index],
                    ],
                }
            )

    return {
        "system": {
            "points_label": "Star Points",
            "points_icon": "mdi:star",
        },
        "assignees": list(ASSIGNEES),
        "approvers": [
            {
                **approver,
                "assignees": assignee_names,
                "mobile_notify_service": "",
            }
            for approver in APPROVERS
        ],
        "chores": chores,
    }


def write_scenario_file(output_dir: Path, chores_per_assignee: int) -> Path:
    """Generate and write one dense scenario YAML file."""
    scenario = build_dense_scenario(chores_per_assignee)
    output_path = output_dir / f"scenario_density_starblum_{chores_per_assignee}.yaml"
    yaml_text = yaml.dump(
        scenario,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=88,
        Dumper=_ScenarioDumper,
    )
    output_path.write_text(yaml_text, encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate dense ChoreOps scenarios for stress testing"
    )
    parser.add_argument(
        "counts",
        nargs="*",
        type=int,
        default=list(DEFAULT_COUNTS),
        help="Chores per assignee to generate. Default: 40 50 60 70 80 90 100",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Directory to write scenarios into. Default: {OUTPUT_DIR}",
    )
    return parser.parse_args()


def main() -> None:
    """Generate the requested dense scenario files."""
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for count in args.counts:
        if count <= 0:
            raise ValueError(f"Count must be positive: {count}")
        output_path = write_scenario_file(output_dir, count)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
