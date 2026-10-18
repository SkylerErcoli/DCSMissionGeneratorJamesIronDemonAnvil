"""User-requested Windows updates from this project's official GitHub releases.

Checks and downloads block, so desktop callers must run them on a worker thread.
Nothing is installed until the caller explicitly invokes ``launch_update``.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import __version__, EXPERIMENTAL, RELEASE_TAG
from .diagnostics import log_path


REPOSITORY_URL = "https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil"
MANIFEST_URL = f"{REPOSITORY_URL}/releases/latest/download/update.json"
INSTALLER_NAME = "IronAnvil-Setup-x64.exe"
MAX_MANIFEST_BYTES = 16 * 1024
MAX_INSTALLER_BYTES = 150 * 1024 * 1024
_CHUNK_BYTES = 64 * 1024
_TIMEOUT_SECONDS = 45
_VERSION = re.compile(r"(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\Z")
_SHA256 = re.compile(r"[a-fA-F0-9]{64}\Z")
_RELEASE_HOSTS = frozenset({
    "github.com", "release-assets.githubusercontent.com",
    "objects.githubusercontent.com", "github-releases.githubusercontent.com",
})


class UpdateError(RuntimeError):
    """An update could not be safely checked, downloaded, or started."""


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    installer_url: str
    sha256: str
    release_url: str


def _version_parts(version: str) -> tuple[int, int, int]:
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise UpdateError("The update has an invalid version number.")
    return tuple(int(part) for part in version.split("."))


def _require_release_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
    except (TypeError, ValueError) as exc:
        raise UpdateError("The update download has an invalid address.") from exc
    if (parsed.scheme != "https" or hostname not in _RELEASE_HOSTS
            or parsed.username is not None or parsed.password is not None
            or parsed.netloc != hostname or parsed.fragment):
        raise UpdateError("The update download did not come from an official GitHub release.")


class _ReleaseRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _require_release_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_release(url: str):
    _require_release_url(url)
    request = Request(url, headers={
        "User-Agent": f"IronAnvil/{__version__}",
        "Accept": "application/octet-stream, application/json",
        "Accept-Encoding": "identity",
    })
    try:
        response = build_opener(_ReleaseRedirectHandler()).open(request, timeout=_TIMEOUT_SECONDS)
        try:
            _require_release_url(response.geturl())
        except UpdateError:
            response.close()
            raise
        return response
    except HTTPError as exc:
        if exc.code == 404:
            raise UpdateError(
                "Update information is not available yet. Try again later or use the Downloads page."
            ) from exc
        raise UpdateError(f"GitHub could not provide the update (HTTP {exc.code}). Try again later.") from exc
    except (URLError, TimeoutError, OSError, HTTPException) as exc:
        raise UpdateError("Could not reach GitHub securely. Check your internet connection and try again.") from exc


def _validate_info(info: UpdateInfo) -> None:
    _version_parts(info.version)
    tag = f"v{info.version}"
    if (info.installer_url != f"{REPOSITORY_URL}/releases/download/{tag}/{INSTALLER_NAME}"
            or info.release_url != f"{REPOSITORY_URL}/releases/tag/{tag}"):
        raise UpdateError("The update does not point to this project's official release.")
    if not isinstance(info.sha256, str) or not _SHA256.fullmatch(info.sha256):
        raise UpdateError("The update is missing a valid SHA-256 checksum.")


def check_for_update(current_version: str | None = None) -> UpdateInfo | None:
    """Return a verified description of a newer stable release, if available."""
    if current_version is None and EXPERIMENTAL:
        raise UpdateError(f"Experimental builds use their own downloads page: {REPOSITORY_URL}/releases/tag/{RELEASE_TAG}")
    current = _version_parts(current_version or __version__)
    try:
        with _open_release(MANIFEST_URL) as response:
            raw = response.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise UpdateError("The update information is unexpectedly large.")
        metadata = json.loads(raw)
        if not isinstance(metadata, dict):
            raise UpdateError("The update information is not in the expected format.")
        version = metadata.get("version")
        latest = _version_parts(version)
        if metadata.get("tag") != f"v{version}" or metadata.get("installer") != INSTALLER_NAME:
            raise UpdateError("The update information has an invalid release or installer name.")
        info = UpdateInfo(
            version=version,
            installer_url=f"{REPOSITORY_URL}/releases/download/v{version}/{INSTALLER_NAME}",
            sha256=metadata.get("sha256"),
            release_url=metadata.get("release_url"),
        )
        _validate_info(info)
        return info if latest > current else None
    except (ValueError, UnicodeError, TypeError) as exc:
        raise UpdateError("The update information could not be read. Try again later.") from exc
    except (TimeoutError, OSError, HTTPException) as exc:
        raise UpdateError("The update check was interrupted. Check your connection and try again.") from exc


def _matches_checksum(path: Path, expected_sha256: str) -> bool:
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_INSTALLER_BYTES:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(_CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest() == expected_sha256.lower()


def download_update(
    info: UpdateInfo,
    progress_callback: Callable[[int, int | None], None] | None = None,
) -> Path:
    """Cache a checksum-verified installer without touching installed user files.

    ``progress_callback(received_bytes, total_bytes)`` runs on the calling thread;
    total_bytes is None when GitHub does not provide a Content-Length header.
    """
    _validate_info(info)
    temporary: Path | None = None
    try:
        directory = log_path().parent.parent / "updates"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"IronAnvil-Setup-{info.version}-x64.exe"
        if _matches_checksum(target, info.sha256):
            if progress_callback:
                progress_callback(target.stat().st_size, target.stat().st_size)
            return target
        # This path belongs only to this updater, never a user's mission or preset.
        target.unlink(missing_ok=True)
        with _open_release(info.installer_url) as response:
            header = response.headers.get("Content-Length")
            try:
                total = int(header) if header is not None else None
            except (TypeError, ValueError) as exc:
                raise UpdateError("The update download has an invalid size.") from exc
            if total is not None and not 0 < total <= MAX_INSTALLER_BYTES:
                raise UpdateError("The update download is empty or unexpectedly large.")
            digest = hashlib.sha256()
            received = 0
            descriptor, name = tempfile.mkstemp(prefix=f"{target.stem}-", suffix=".part", dir=directory)
            temporary = Path(name)
            with os.fdopen(descriptor, "wb") as destination:
                while block := response.read(_CHUNK_BYTES):
                    received += len(block)
                    if received > MAX_INSTALLER_BYTES or (total is not None and received > total):
                        raise UpdateError("The update download is larger than expected.")
                    digest.update(block)
                    destination.write(block)
                    if progress_callback:
                        progress_callback(received, total)
            if not received or (total is not None and received != total):
                raise UpdateError("The update download was incomplete. Please try again.")
            if digest.hexdigest() != info.sha256.lower():
                raise UpdateError("The update failed its SHA-256 security check. It was not installed.")
        os.replace(temporary, target)
        temporary = None
        return target
    except (TimeoutError, OSError, HTTPException) as exc:
        raise UpdateError("The update could not be downloaded or saved. Check your connection and disk space.") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def launch_update(path: Path, expected_sha256: str) -> subprocess.Popen:
    """Start the normal in-place upgrade wizard; close the GUI only on success.

    Inno Setup retains the existing installation directory and upgrades its files.
    Missions, preferences, and logs live outside that directory and are preserved.
    """
    if sys.platform != "win32":
        raise UpdateError("Automatic installation is available on Windows. Download the new version from Releases.")
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        raise UpdateError("The update is missing verification information. Check for updates again.")
    try:
        installer = Path(path).resolve(strict=True)
        if installer.suffix.lower() != ".exe" or not _matches_checksum(installer, expected_sha256):
            raise UpdateError("The downloaded installer failed verification. Check for updates again.")
        return subprocess.Popen([str(installer), "/NORESTART", "/SP-"])
    except OSError as exc:
        raise UpdateError("Windows could not start the update. Please try again or download it from Releases.") from exc
