"""User preferences kept outside the application so upgrades retain them."""
from collections.abc import Mapping
import json
import logging
import os
from pathlib import Path
import tempfile

from .diagnostics import log_path


def preferences_path() -> Path:
    return log_path().parent.parent / "preferences.json"


def _read(path):
    with path.open(encoding="utf-8") as source:
        contents = json.load(source)
    if not isinstance(contents, dict):
        raise ValueError("Saved preferences must contain an object")
    return contents


def load_preferences() -> dict:
    path = preferences_path()
    try:
        return _read(path)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        logging.warning("Could not read preferences from %s", path, exc_info=True)
        return {}


def _merged(existing, updates):
    result = dict(existing)
    for key, value in updates.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = _merged(result[key], value)
        else:
            result[key] = value
    return result


def save_preferences(updates: Mapping) -> None:
    """Merge settings atomically, preserving unknown keys and damaged files."""
    if not isinstance(updates, Mapping):
        raise TypeError("Preferences must be a mapping")
    path = preferences_path()
    try:
        existing = _read(path)
    except FileNotFoundError:
        existing = {}
    # A damaged or inaccessible existing file is left intact for recovery.
    contents = json.dumps(_merged(existing, updates), indent=2, sort_keys=True, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".preferences-", suffix=".tmp", delete=False) as target:
            temporary = Path(target.name)
            target.write(contents + "\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
