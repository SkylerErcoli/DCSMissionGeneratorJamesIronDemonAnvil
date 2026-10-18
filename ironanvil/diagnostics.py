"""Per-user diagnostics for desktop and bundled launches."""
from logging.handlers import RotatingFileHandler
import logging
import os
from pathlib import Path
from . import APP_DATA_NAME


def log_path() -> Path:
    """Return a writable user-data location, never the program's install folder."""
    override = os.environ.get("IRONANVIL_DATA_DIR")
    if override:
        base = Path(override)
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_DATA_NAME
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / APP_DATA_NAME
    return base / "logs" / "ironanvil.log"


def configure_logging() -> Path:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if not any(isinstance(handler, RotatingFileHandler)
               and Path(handler.baseFilename) == path.resolve() for handler in root.handlers):
        handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    return path
