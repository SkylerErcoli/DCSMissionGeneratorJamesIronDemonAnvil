"""Exercise the updater without network access or executing an installer."""
import hashlib
from http.client import IncompleteRead
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from ironanvil import updater


PAYLOAD = b"A test installer, never executable."
SHA256 = hashlib.sha256(PAYLOAD).hexdigest()


class Response(io.BytesIO):
    def __init__(self, payload, content_length=None, url=None):
        super().__init__(payload)
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}
        self.url = url or updater.MANIFEST_URL

    def geturl(self):
        return self.url


def manifest(version="1.10.0", **overrides):
    result = {
        "version": version,
        "tag": f"v{version}",
        "installer": updater.INSTALLER_NAME,
        "sha256": SHA256,
        "release_url": f"{updater.REPOSITORY_URL}/releases/tag/v{version}",
    }
    result.update(overrides)
    return result


def information(version="1.10.0"):
    return updater.UpdateInfo(
        version=version,
        installer_url=f"{updater.REPOSITORY_URL}/releases/download/v{version}/{updater.INSTALLER_NAME}",
        sha256=SHA256,
        release_url=f"{updater.REPOSITORY_URL}/releases/tag/v{version}",
    )


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("IRONANVIL_DATA_DIR", str(tmp_path / "userdata"))


def set_manifest(monkeypatch, data):
    raw = data if isinstance(data, bytes) else json.dumps(data).encode()
    monkeypatch.setattr(updater, "_open_release", lambda url: Response(raw))


def test_update_compares_numeric_versions_and_builds_immutable_official_url(monkeypatch):
    set_manifest(monkeypatch, manifest("1.10.0"))
    info = updater.check_for_update("1.9.0")
    assert info == information("1.10.0")
    assert "/releases/download/v1.10.0/" in info.installer_url


@pytest.mark.parametrize("version", ["1.9.0", "1.8.99", "0.99.0"])
def test_equal_or_older_release_never_downgrades(monkeypatch, version):
    set_manifest(monkeypatch, manifest(version))
    assert updater.check_for_update("1.9.0") is None


@pytest.mark.parametrize("data", [
    b"not json",
    b"\xff",
    b"[]",
    b"null",
    manifest("01.10.0"),
    manifest("1.10.0-beta"),
    manifest(tag="v9.0.0"),
    manifest(installer="another-program.exe"),
    manifest(sha256="missing"),
    manifest(sha256=None),
    manifest(release_url="https://github.com/attacker/repo/releases/tag/v1.10.0"),
])
def test_malformed_or_untrusted_metadata_cannot_be_used(monkeypatch, data):
    set_manifest(monkeypatch, data)
    with pytest.raises(updater.UpdateError):
        updater.check_for_update("1.9.0")


def test_metadata_size_is_limited(monkeypatch):
    set_manifest(monkeypatch, b" " * (updater.MAX_MANIFEST_BYTES + 1))
    with pytest.raises(updater.UpdateError, match="unexpectedly large"):
        updater.check_for_update("1.9.0")


@pytest.mark.parametrize("url", [
    "http://github.com/owner/repo",
    "https://github.com.attacker.example/installer.exe",
    "https://github.com@attacker.example/installer.exe",
    "https://attacker.example/installer.exe",
    "https://github.com:444/installer.exe",
    "https://user@github.com/installer.exe",
])
def test_redirects_reject_plain_http_untrusted_hosts_and_credentials(url):
    handler = updater._ReleaseRedirectHandler()
    with pytest.raises(updater.UpdateError, match="official GitHub"):
        handler.redirect_request(Request(updater.MANIFEST_URL), None, 302, "Found", {}, url)


def test_redirects_allow_github_release_asset_cdn():
    url = "https://release-assets.githubusercontent.com/github-production-release-asset/123/file?signature=example"
    request = updater._ReleaseRedirectHandler().redirect_request(
        Request(updater.MANIFEST_URL), None, 302, "Found", {}, url,
    )
    assert request.full_url == url


def test_untrusted_final_response_is_closed_before_rejection(monkeypatch):
    response = Response(PAYLOAD, url="https://attacker.example/update.json")

    class RedirectedOpener:
        def open(self, *args, **kwargs):
            return response

    monkeypatch.setattr(updater, "build_opener", lambda *args: RedirectedOpener())
    with pytest.raises(updater.UpdateError, match="official GitHub"):
        updater.check_for_update("1.9.0")
    assert response.closed


@pytest.mark.parametrize("exception, message", [
    (HTTPError(updater.MANIFEST_URL, 404, "not found", {}, None), "not available yet"),
    (HTTPError(updater.MANIFEST_URL, 503, "unavailable", {}, None), "HTTP 503"),
    (URLError("certificate verify failed"), "securely"),
    (TimeoutError(), "securely"),
])
def test_network_errors_have_recovery_messages(monkeypatch, exception, message):
    class FailedOpener:
        def open(self, *args, **kwargs):
            raise exception

    monkeypatch.setattr(updater, "build_opener", lambda *args: FailedOpener())
    with pytest.raises(updater.UpdateError, match=message):
        updater.check_for_update("1.9.0")


def test_verified_download_is_atomic_and_valid_cache_does_not_need_network(monkeypatch, tmp_path):
    calls = []

    def download(url):
        calls.append(url)
        return Response(PAYLOAD, len(PAYLOAD), url)

    monkeypatch.setattr(updater, "_open_release", download)
    progress = []
    path = updater.download_update(information(), lambda received, total: progress.append((received, total)))
    assert path.read_bytes() == PAYLOAD
    assert path.parent == tmp_path / "userdata" / "updates"
    assert progress[-1] == (len(PAYLOAD), len(PAYLOAD))
    assert list(path.parent.glob("*.part")) == []
    assert updater.download_update(information()) == path
    assert calls == [information().installer_url]


def test_unknown_content_length_can_be_verified(monkeypatch):
    monkeypatch.setattr(updater, "_open_release", lambda url: Response(PAYLOAD))
    progress = []
    path = updater.download_update(information(), lambda received, total: progress.append((received, total)))
    assert path.read_bytes() == PAYLOAD
    assert progress[-1] == (len(PAYLOAD), None)


def test_corrupt_cache_is_redownloaded_without_removing_other_files(monkeypatch, tmp_path):
    directory = tmp_path / "userdata" / "updates"
    directory.mkdir(parents=True)
    target = directory / "IronAnvil-Setup-1.10.0-x64.exe"
    target.write_bytes(b"corrupt")
    other = directory / "unrelated-user-file.txt"
    other.write_text("keep")
    monkeypatch.setattr(updater, "_open_release", lambda url: Response(PAYLOAD))
    assert updater.download_update(information()) == target
    assert target.read_bytes() == PAYLOAD
    assert other.read_text() == "keep"


@pytest.mark.parametrize("payload, length, error", [
    (b"untrusted bytes", None, "SHA-256"),
    (PAYLOAD[:5], len(PAYLOAD), "incomplete"),
    (PAYLOAD, 1, "larger than expected"),
    (b"", None, "incomplete"),
    (PAYLOAD, "not-a-size", "invalid size"),
    (PAYLOAD, updater.MAX_INSTALLER_BYTES + 1, "unexpectedly large"),
])
def test_bad_downloads_are_never_kept_or_installed(monkeypatch, tmp_path, payload, length, error):
    monkeypatch.setattr(updater, "_open_release", lambda url: Response(payload, length))
    with pytest.raises(updater.UpdateError, match=error):
        updater.download_update(information())
    assert list((tmp_path / "userdata" / "updates").iterdir()) == []


def test_streamed_download_without_length_is_still_bounded(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "MAX_INSTALLER_BYTES", 5)
    monkeypatch.setattr(updater, "_open_release", lambda url: Response(PAYLOAD))
    with pytest.raises(updater.UpdateError, match="larger than expected"):
        updater.download_update(information())
    assert list((tmp_path / "userdata" / "updates").iterdir()) == []


def test_interrupted_download_discards_part_file(monkeypatch, tmp_path):
    class InterruptedResponse(Response):
        def read(self, size):
            if self.tell():
                raise ConnectionResetError("connection interrupted")
            return super().read(5)

    monkeypatch.setattr(updater, "_open_release", lambda url: InterruptedResponse(PAYLOAD))
    with pytest.raises(updater.UpdateError, match="connection and disk space"):
        updater.download_update(information())
    assert list((tmp_path / "userdata" / "updates").iterdir()) == []


def test_abrupt_http_response_discards_partial_download(monkeypatch, tmp_path):
    class TruncatedResponse(Response):
        def read(self, size):
            raise IncompleteRead(b"partial bytes")

    monkeypatch.setattr(updater, "_open_release", lambda url: TruncatedResponse(PAYLOAD))
    with pytest.raises(updater.UpdateError, match="connection and disk space"):
        updater.download_update(information())
    assert list((tmp_path / "userdata" / "updates").iterdir()) == []


def test_manually_constructed_untrusted_info_is_rejected_before_download(monkeypatch):
    monkeypatch.setattr(updater, "_open_release", lambda url: pytest.fail("must not make request"))
    info = updater.UpdateInfo("1.10.0", "https://attacker.example/update.exe", SHA256, information().release_url)
    with pytest.raises(updater.UpdateError, match="official release"):
        updater.download_update(info)


def test_windows_upgrade_is_visible_and_verifies_file_before_start(monkeypatch, tmp_path):
    path = tmp_path / "installer.exe"
    path.write_bytes(PAYLOAD)
    process = object()
    commands = []
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater.subprocess, "Popen", lambda command: commands.append(command) or process)
    assert updater.launch_update(path, SHA256) is process
    assert commands == [[str(path.resolve()), "/NORESTART", "/SP-"]]


def test_tampered_installer_cannot_be_launched(monkeypatch, tmp_path):
    path = tmp_path / "installer.exe"
    path.write_bytes(b"tampered")
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater.subprocess, "Popen", lambda *args: pytest.fail("must not start"))
    with pytest.raises(updater.UpdateError, match="failed verification"):
        updater.launch_update(path, SHA256)


def test_failed_windows_start_does_not_report_success(monkeypatch, tmp_path):
    path = tmp_path / "installer.exe"
    path.write_bytes(PAYLOAD)
    monkeypatch.setattr(updater.sys, "platform", "win32")

    def fail(command):
        raise PermissionError("Windows refused to run this file")

    monkeypatch.setattr(updater.subprocess, "Popen", fail)
    with pytest.raises(updater.UpdateError, match="could not start"):
        updater.launch_update(path, SHA256)


def test_other_platforms_get_download_instructions(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.sys, "platform", "linux")
    with pytest.raises(updater.UpdateError, match="available on Windows"):
        updater.launch_update(tmp_path / "installer.exe", SHA256)
