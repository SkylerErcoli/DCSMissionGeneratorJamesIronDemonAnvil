"""A published updater manifest identifies and hashes its exact release asset."""
import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def manifest_writer():
    path = Path(__file__).resolve().parents[1] / "tools/write_update_manifest.py"
    spec = importlib.util.spec_from_file_location("write_update_manifest", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_installer_checksum_and_immutable_version(manifest_writer, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.0"\n')
    installer = tmp_path / manifest_writer.INSTALLER
    installer.write_bytes(b"the actual executable, not a placeholder checksum")
    destination = tmp_path / "assets/update.json"
    actual = manifest_writer.write_manifest(tmp_path, installer, destination)
    assert json.loads(destination.read_text()) == actual
    assert actual == {
        "version": "1.2.0", "tag": "v1.2.0", "installer": installer.name,
        "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
        "release_url": f"{manifest_writer.REPOSITORY}/releases/tag/v1.2.0",
    }


@pytest.mark.parametrize("version", ["1.2", "1.2.0rc1", "01.2.0", "1.2.0/escape"])
def test_only_stable_release_versions(manifest_writer, tmp_path, version):
    (tmp_path / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n')
    installer = tmp_path / manifest_writer.INSTALLER
    installer.write_bytes(b"installer")
    with pytest.raises(ValueError, match="stable"):
        manifest_writer.write_manifest(tmp_path, installer, tmp_path / "update.json")
    assert not (tmp_path / "update.json").exists()


@pytest.mark.parametrize("name,content", [("different.exe", b"installer"), ("IronAnvil-Setup-x64.exe", b"")])
def test_reject_missing_or_wrong_release_artifact(manifest_writer, tmp_path, name, content):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.0"\n')
    installer = tmp_path / name
    installer.write_bytes(content)
    with pytest.raises(ValueError, match="nonempty"):
        manifest_writer.write_manifest(tmp_path, installer, tmp_path / "update.json")
