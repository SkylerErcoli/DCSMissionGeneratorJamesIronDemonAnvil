"""Create release metadata from the exact Windows installer being published."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tomllib


REPOSITORY = "https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil"
INSTALLER = "IronAnvil-Setup-x64.exe"


def write_manifest(repository: Path, installer: Path, destination: Path) -> dict:
    with (repository / "pyproject.toml").open("rb") as source:
        version = tomllib.load(source)["project"]["version"]
    if not isinstance(version, str) or not re.fullmatch(r"(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})", version):
        raise ValueError("A stable major.minor.patch version is required")
    if installer.name != INSTALLER or not installer.is_file() or not installer.stat().st_size:
        raise ValueError(f"The nonempty release installer must be named {INSTALLER}")
    with installer.open("rb") as source:
        checksum = hashlib.file_digest(source, "sha256").hexdigest()
    metadata = {"version": version, "tag": f"v{version}", "installer": INSTALLER,
                "sha256": checksum, "release_url": f"{REPOSITORY}/releases/tag/v{version}"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--installer", type=Path, default=Path("dist") / INSTALLER)
    parser.add_argument("--output", type=Path, default=Path("dist/update.json"))
    args = parser.parse_args()
    write_manifest(args.repository, args.installer, args.output)


if __name__ == "__main__":
    main()
