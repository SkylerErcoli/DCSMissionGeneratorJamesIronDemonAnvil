"""Exercise the bundled mission controller against DCS API doubles in Lua 5.1."""
from pathlib import Path
import os
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    "ground_objective_and_friendly_recovery",
    "cap_activation_and_defeat",
    "cap_disabled_station_time",
    "convoy_hold_and_road_routing",
    "convoy_road_fallbacks",
    "f10_current_target_position",
    "air_start_and_human_client_filter",
    "static_objectives_and_empty_configuration",
    "all_surviving_clients_must_recover",
    "joined_idle_client_must_fly_and_return",
    "loss_excludes_dead_client_from_recovery",
    "all_clients_lost_fails_mission",
    "birth_registers_late_joined_client",
    "cap_activation_retries_documented_api",
    "cap_waits_for_actual_spawn",
    "operation_functional_threshold_and_shared_recovery",
    "operation_bonus_delays_once_and_dispatches",
    "operation_bonus_cancels_before_dispatch",
    "operation_late_bonus_does_not_remove_response",
    "operation_unseen_targets_are_not_destroyed",
    "operation_response_retries_are_bounded",
    "operation_staged_force_can_be_interdicted",
    "operation_failure_keeps_partial_debrief",
    "operation_bonus_after_main_before_recovery",
    "operation_staging_mark_is_available_to_the_team",
    "convoy_operation_counts_supply_trucks_not_escorts",
    "convoy_delivery_accelerates_only_one_response",
    "convoy_delivery_respects_cancelled_response",
    "convoy_operation_f10_tracks_moving_cargo",
    "withdrawal_needs_confirmation_and_all_survivors",
    "withdrawal_proposal_expiry_cancel_and_disabled_option",
    "withdrawal_keeps_parked_teammates_safe_without_awarding_flight_points",
    "withdrawal_can_upgrade_to_full_success_and_loss_still_fails",
    "approved_alternate_allows_split_team_recovery",
    "alternate_rejects_hostile_and_unlisted_airfields",
    "alternate_helipad_event_without_place_checks_coalition",
    "search_intelligence_withholds_exact_marks_and_requires_airborne_checkin",
    "search_checkin_resets_if_team_leaves_and_does_not_count_parked_clients",
    "search_checkin_needs_live_area_presence_at_confirmation",




)


@pytest.fixture(scope="module")
def lua51():
    executable = os.environ.get("LUA51") or shutil.which("lua5.1") or shutil.which("lua")
    if not executable:
        pytest.skip("Lua 5.1 unavailable; install it or set LUA51")
    version = subprocess.run([executable, "-v"], capture_output=True, text=True, check=False)
    assert version.returncode == 0, version.stdout + version.stderr
    assert "Lua 5.1" in version.stdout + version.stderr, "Set LUA51 to a Lua 5.1 executable"
    return executable


@pytest.mark.parametrize("case", CASES)
def test_dcs_runtime(lua51, case):
    result = subprocess.run(
        [lua51, str(ROOT / "tests" / "runtime_harness.lua"),
         str(ROOT / "ironanvil" / "runtime.lua"), case],
        capture_output=True, text=True, check=False, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: " + case in result.stdout
