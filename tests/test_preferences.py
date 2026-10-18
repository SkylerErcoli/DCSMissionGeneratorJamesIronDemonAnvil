"""Settings must survive an upgrade, future options, and interrupted writes."""
import json
from unittest.mock import patch

import pytest

from ironanvil.preferences import load_preferences, preferences_path, save_preferences


@pytest.fixture(autouse=True)
def user_data(tmp_path, monkeypatch):
    monkeypatch.setenv("IRONANVIL_DATA_DIR", str(tmp_path / "User data"))


def test_preferences_merge_without_losing_future_options():
    save_preferences({"theme": "dark", "mission": {"output": "D:/My Missions", "future_option": 7},
                      "unknown_root": "retain"})
    save_preferences({"theme": "light", "mission": {"departure": "Damascus"}})
    assert load_preferences() == {
        "theme": "light", "mission": {"output": "D:/My Missions", "departure": "Damascus", "future_option": 7},
        "unknown_root": "retain"}


def test_interrupted_save_preserves_original_preferences():
    save_preferences({"theme": "dark"})
    before = preferences_path().read_bytes()
    with patch("ironanvil.preferences.os.replace", side_effect=OSError("disk is unavailable")):
        with pytest.raises(OSError):
            save_preferences({"theme": "light"})
    assert preferences_path().read_bytes() == before
    assert not list(preferences_path().parent.glob(".preferences-*.tmp"))


def test_damaged_preferences_do_not_prevent_opening_or_get_overwritten():
    path = preferences_path()
    path.parent.mkdir(parents=True)
    path.write_text("{damaged", encoding="utf-8")
    assert load_preferences() == {}
    with pytest.raises(json.JSONDecodeError):
        save_preferences({"theme": "dark"})
    assert path.read_text(encoding="utf-8") == "{damaged"
