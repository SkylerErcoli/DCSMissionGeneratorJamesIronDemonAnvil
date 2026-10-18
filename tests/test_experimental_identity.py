"""Experimental builds must never replace or update the friends' stable copy."""
from pathlib import Path

import pytest

from ironanvil import APP_DATA_NAME
from ironanvil import diagnostics, model, updater


def test_default_experimental_update_never_contacts_stable_feed(monkeypatch):
    monkeypatch.setattr(updater, '_open_release', lambda *_: pytest.fail('Contacted stable update feed'))
    with pytest.raises(updater.UpdateError, match='Experimental builds'):
        updater.check_for_update()


def test_preferences_and_outputs_are_outside_stable_directories(monkeypatch, tmp_path):
    monkeypatch.delenv('IRONANVIL_DATA_DIR', raising=False)
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    assert APP_DATA_NAME == 'IronAnvilExperimental'
    if diagnostics.os.name != 'nt':
        assert diagnostics.log_path().relative_to(tmp_path).parts[0] == APP_DATA_NAME
    assert APP_DATA_NAME in model.default_output_dir().parts


def test_installer_identity_and_default_location_are_separate():
    text=(Path(__file__).resolve().parents[1]/'packaging/installer.iss').read_text()
    assert '2C791DDC-1A55-4FAE-BAB3-30819BF2869D' not in text
    assert 'AppId={{F698B14E-6D10-4A68-BB62-A75C5DCC04F2}' in text
    assert r'DefaultDirName={localappdata}\Programs\IronAnvilExperimental' in text
    assert 'AppName=Iron Anvil Experimental' in text
