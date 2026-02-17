"""Compatibility package alias for legacy custom_components.kidschores imports."""

from pathlib import Path
import warnings

from custom_components.choreops import *  # noqa: F403

warnings.warn(
    "custom_components.kidschores is deprecated and will be removed in v0.5.0 final; "
    "use custom_components.choreops instead",
    DeprecationWarning,
    stacklevel=2,
)

# Allow legacy submodule imports like custom_components.kidschores.helpers.*
__path__ = [str(Path(__file__).resolve().parent.parent / "choreops")]
