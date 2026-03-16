"""Boot-time integrity repair entry points for modern storage payloads."""

from .boot_repairs import repair_impossible_due_state_residue, run_boot_repairs

__all__ = [
    "repair_impossible_due_state_residue",
    "run_boot_repairs",
]
