# File: utils/__init__.py
"""Pure Python utilities for KidsChores.

This module contains pure Python functions with ZERO Home Assistant dependencies.
All functions here can be unit tested without Home Assistant mocking.

⚠️ DIRECTIVE 1 - UTILS PURITY: NO `homeassistant.*` imports allowed in this module.
   Violation causes Phase 7.1 FAILURE.

Submodules:
    - dt_utils: Date/time parsing, formatting, scheduling calculations
    - math_utils: Point rounding, multiplier arithmetic, progress calculations

Usage:
    from . import dt_utils
    from .math_utils import round_points
"""

from . import dt_utils, math_utils

__all__ = ["dt_utils", "math_utils"]
