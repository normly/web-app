# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Rollback: export the deletions made since the backup, replay them after the restore."""

import glob
import json
import tempfile

from test_deploy_kb import TOMB_LISTING, _rollback, _seed

ACCOUNT = "11111111-1111-4111-8111-111111111111"
CHAT = "22222222-2222-4222-8222-222222222222"


def _doc(*entries):
    return json.dumps({
        "format": 1, "created_at": "2026-10-10T00:00:00+00:00",
        "entries": [
            {"kind": kind, "entity_id": entity, "deleted_at": "2026-10-09T12:00:00+00:00"}
            for kind, entity in entries
        ],
    })


FULL = _doc(("account", ACCOUNT), ("chat_session", CHAT))


def _index(calls, needle):
    return next(i for i, c in enumerate(calls) if needle in c)


def test_export_runs_with_the_current_release_before_anything_destructive(harness):
    _seed(harness)
    result = _rollback(harness, "--yes", extra_env={"FAKE_DOCKER_DELETIONS_OUT": FULL})
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    export = _index(calls, "export-deletions")
    assert "--since 2026-10-09T09:00:00+00:00" in calls[export]
    assert "run --rm --no-deps -T --entrypoint python pipeline" in calls[export]
    first_destructive = next(
        i for i, c in enumerate(calls)
        if " down" in c or c.startswith(("age", "pg_restore")) or "DROP TABLE" in c
    )
    assert export < first_destructive


def test_export_failure_aborts_before_any_change(harness):
    state = _seed(harness)
    result = _rollback(
        harness, extra_env={"FAKE_DOCKER_FAIL_ON": "export-deletions"}, input_text="0.1.1\n",
    )
    assert result.returncode != 0
    assert "deletion" in result.stderr and "nothing was changed" in result.stderr
    assert "Type the target tag" not in result.stderr
    calls = harness.calls()
    assert not any(" down" in c for c in calls)
    assert not any(c.startswith("pg_restore") or "DROP TABLE" in c for c in calls)
    assert (state / "current_tag").read_text().strip() == "0.1.2"
    assert not (state / "deploy.lock").exists()


def test_an_invalid_deletion_document_aborts_before_the_prompt(harness):
    _seed(harness)
    for bad in ("", "not json", '{"format": 2}', _doc(("account", "nope"))):
        result = _rollback(
            harness, extra_env={"FAKE_DOCKER_DELETIONS_OUT": bad}, input_text="0.1.1\n",
        )
        assert result.returncode != 0, bad
        assert "nothing was changed" in result.stderr
        assert "Type the target tag" not in result.stderr
    assert not any(" down" in c for c in harness.calls())


def test_a_supporting_previous_release_replays_after_the_restore(harness, tmp_path):
    _seed(harness)
    stdin_file = tmp_path / "replay-stdin"
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": FULL, "FAKE_RCLONE_OUT": TOMB_LISTING,
                   "FAKE_PSQL_OUT": "account", "FAKE_DOCKER_REPLAY_STDIN_FILE": str(stdin_file)},
    )
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    check = _index(calls, "replay-deletions --check")
    tombs = _index(calls, "exchange import-tombstones")
    restore = next(i for i, c in enumerate(calls) if c.startswith("pg_restore"))
    replay = next(
        i for i, c in enumerate(calls)
        if "replay-deletions" in c and "--check" not in c
    )
    up = _index(calls, " up -d")
    assert check < _index(calls, " down")
    assert tombs < restore < replay < up
    assert "run --rm --no-deps -T --entrypoint python pipeline" in calls[replay]
    assert json.loads(stdin_file.read_text())["entries"][0]["entity_id"] == ACCOUNT
    assert "cannot replay deletions" not in result.stderr
    assert result.stderr.count("account:") == 0


def test_the_check_and_the_replay_use_the_previous_release_image(harness):
    _seed(harness)
    (harness.dir / "releases" / "0.1.2").mkdir(parents=True, exist_ok=True)
    result = _rollback(harness, "--yes", extra_env={"FAKE_DOCKER_DELETIONS_OUT": FULL})
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    assert "releases/0.1.2/compose.yaml" in calls[_index(calls, "export-deletions")]
    assert "releases/0.1.1/compose.yaml" in calls[_index(calls, "replay-deletions --check")]
    replay = next(c for c in calls if "replay-deletions" in c and "--check" not in c)
    assert "releases/0.1.1/compose.yaml" in replay


def test_a_previous_release_without_the_command_gets_a_banner_and_continues(harness):
    state = _seed(harness)
    result = _rollback(
        harness,
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": FULL, "FAKE_DOCKER_REPLAY_CHECK_EXIT": "2"},
        input_text="0.1.1\n",
    )
    assert result.returncode == 0, result.stderr
    banner = (
        "previous release cannot replay deletions; re-delete these by hand after the "
        f"rollback (2, first 20: account:{ACCOUNT}, chat_session:{CHAT})"
    )
    assert banner in result.stderr
    assert result.stderr.index(banner) < result.stderr.index("Type the target tag")
    calls = harness.calls()
    assert not any("replay-deletions" in c and "--check" not in c for c in calls)
    assert any(c.startswith("pg_restore") for c in calls)
    assert (state / "current_tag").read_text().strip() == "0.1.1"


def test_an_unsupported_replay_still_needs_the_confirmation(harness):
    state = _seed(harness)
    result = _rollback(
        harness,
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": FULL, "FAKE_DOCKER_REPLAY_CHECK_EXIT": "2"},
        input_text="no\n",
    )
    assert result.returncode != 0
    assert "aborted" in result.stderr
    assert not any(" down" in c for c in harness.calls())
    assert (state / "current_tag").read_text().strip() == "0.1.2"


def test_an_empty_list_makes_no_replay_call(harness):
    _seed(harness)
    result = _rollback(harness, "--yes")
    assert result.returncode == 0, result.stderr
    assert any("export-deletions" in c for c in harness.calls())
    assert not any("replay-deletions" in c for c in harness.calls())
    assert "cannot replay deletions" not in result.stderr


def test_an_empty_list_needs_no_banner_even_without_support(harness):
    _seed(harness)
    result = _rollback(harness, "--yes", extra_env={"FAKE_DOCKER_REPLAY_CHECK_EXIT": "2"})
    assert result.returncode == 0, result.stderr
    assert "cannot replay deletions" not in result.stderr


def test_a_replay_failure_after_the_drop_prints_recovery_guidance(harness):
    state = _seed(harness)
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": FULL, "FAKE_DOCKER_REPLAY_EXIT": "1"},
    )
    assert result.returncode != 0
    assert "dropped and is incomplete" in result.stderr
    assert "current_tag is still 0.1.2" in result.stderr
    assert not any(" up -d" in c for c in harness.calls())
    assert not (state / "deploy.lock").exists()
    assert (state / "current_tag").read_text().strip() == "0.1.2"
    assert (state / "previous_tag").read_text().strip() == "0.1.1"


def test_no_decrypted_deletions_stay_behind(harness, tmp_path):
    _seed(harness)
    before = set(glob.glob(f"{tempfile.gettempdir()}/normly-rollback.*"))
    result = _rollback(harness, "--yes", extra_env={"FAKE_DOCKER_DELETIONS_OUT": FULL})
    assert result.returncode == 0, result.stderr
    assert set(glob.glob(f"{tempfile.gettempdir()}/normly-rollback.*")) == before


def test_the_backup_name_gives_the_timestamp(harness):
    state = _seed(harness)
    (state / "pre_rollout_backup").write_text("20270102T030405Z-daily\n")
    result = _rollback(harness, "--yes")
    assert result.returncode == 0, result.stderr
    export = next(c for c in harness.calls() if "export-deletions" in c)
    assert "--since 2027-01-02T02:04:05+00:00" in export


ONE = _doc(("account", ACCOUNT))


def test_exactly_one_entry_reaches_the_banner_and_the_replay(harness):
    _seed(harness)
    result = _rollback(harness, "--yes", extra_env={"FAKE_DOCKER_DELETIONS_OUT": ONE})
    assert result.returncode == 0, result.stderr
    assert "1 deletion(s) made since the backup will be replayed" in result.stderr
    assert any("replay-deletions" in c and "--check" not in c for c in harness.calls())


def test_exactly_one_unsupported_entry_reaches_the_banner(harness):
    _seed(harness)
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": ONE, "FAKE_DOCKER_REPLAY_CHECK_EXIT": "2"},
    )
    assert result.returncode == 0, result.stderr
    assert f"(1, first 20: account:{ACCOUNT})" in result.stderr


def test_zero_entries_reach_the_banner(harness):
    _seed(harness)
    result = _rollback(harness, "--yes")
    assert result.returncode == 0, result.stderr
    assert "Rollback 0.1.2 -> 0.1.1" in result.stderr


def test_the_replayed_list_is_a_second_export_taken_after_the_stop(harness, tmp_path):
    _seed(harness)
    stdin_file = tmp_path / "replay-stdin"
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": ONE, "FAKE_DOCKER_REPLAY_STDIN_FILE": str(stdin_file)},
    )
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    exports = [i for i, c in enumerate(calls) if "export-deletions" in c]
    assert len(exports) == 2
    down = _index(calls, " down")
    drop = next(i for i, c in enumerate(calls) if c.startswith("psql") and "DROP TABLE" in c)
    assert exports[0] < down < exports[1] < drop
    assert "--since" in calls[exports[1]] and calls[exports[0]].split("--since")[1] == calls[exports[1]].split("--since")[1]
    assert json.loads(stdin_file.read_text())["entries"][0]["entity_id"] == ACCOUNT


def test_the_replay_uses_the_final_export_not_the_first(harness, tmp_path):
    _seed(harness)
    counter = tmp_path / "n"
    # first call prints ONE, later calls print FULL: emulate via a wrapper env switch
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": ONE, "FAKE_DOCKER_DELETIONS_SECOND_OUT": FULL,
                   "FAKE_DOCKER_COUNTER": str(counter),
                   "FAKE_DOCKER_REPLAY_STDIN_FILE": str(tmp_path / "stdin")},
    )
    assert result.returncode == 0, result.stderr
    assert len(json.loads((tmp_path / "stdin").read_text())["entries"]) == 2


def test_a_failing_second_export_stops_before_the_drop(harness):
    state = _seed(harness)
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": ONE, "FAKE_DOCKER_DELETIONS_SECOND_OUT": "garbage",
                   "FAKE_DOCKER_COUNTER": str(harness.dir / "n")},
    )
    assert result.returncode != 0
    assert "services were stopped, database unchanged" in result.stderr
    assert "dropped and is incomplete" not in result.stderr
    calls = harness.calls()
    assert any(" down" in c for c in calls)
    assert not any("DROP TABLE" in c or c.startswith("pg_restore") for c in calls)
    assert (state / "current_tag").read_text().strip() == "0.1.2"
    assert not (state / "deploy.lock").exists()


def test_a_missing_deletion_log_table_means_an_empty_list_without_an_image_call(harness):
    _seed(harness)
    result = _rollback(
        harness, "--yes", extra_env={"FAKE_PSQL_REGCLASS": "", "FAKE_DOCKER_DELETIONS_OUT": FULL},
    )
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    assert not any("export-deletions" in c or "replay-deletions" in c for c in calls)
    assert sum("to_regclass" in c for c in calls) == 2


def test_a_check_failure_other_than_unknown_command_aborts_before_the_prompt(harness):
    state = _seed(harness)
    result = _rollback(
        harness,
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": ONE, "FAKE_DOCKER_REPLAY_CHECK_EXIT": "1"},
        input_text="0.1.1\n",
    )
    assert result.returncode != 0
    assert "nothing was changed" in result.stderr
    assert "Type the target tag" not in result.stderr
    assert not any(" down" in c for c in harness.calls())
    assert (state / "current_tag").read_text().strip() == "0.1.2"


def test_the_unsupported_list_survives_in_the_state_directory(harness):
    state = _seed(harness)
    many = _doc(*[("chat_session", f"00000000-0000-4000-8000-{i:012d}") for i in range(25)])
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": many, "FAKE_DOCKER_REPLAY_CHECK_EXIT": "2"},
    )
    assert result.returncode == 0, result.stderr
    assert "(25, first 20:" in result.stderr and "... and 5 more" in result.stderr
    assert "rollback-pending-deletions.json" in result.stderr
    pending = state / "rollback-pending-deletions.json"
    assert len(json.loads(pending.read_text())["entries"]) == 25
    assert oct(pending.stat().st_mode & 0o777) == "0o600"
    assert not list(state.glob(".rollback-pending*"))


def test_after_a_failed_rollout_the_export_uses_the_failed_release(harness):
    state = _seed(harness)
    (state / "failed_rollout").write_text("0.1.3\n")
    (harness.dir / "releases" / "0.1.3").mkdir(parents=True, exist_ok=True)
    result = _rollback(harness, "--yes")
    assert result.returncode == 0, result.stderr
    exports = [c for c in harness.calls() if "export-deletions" in c]
    assert exports and all("releases/0.1.3/compose.yaml" in c for c in exports)
