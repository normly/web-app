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
    assert "--since 2026-10-09T10:00:00+00:00" in calls[export]
    assert "run --rm --no-deps -T --entrypoint python pipeline" in calls[export]
    first_destructive = next(
        i for i, c in enumerate(calls)
        if " down" in c or c.startswith(("psql", "age", "pg_restore"))
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
    assert not any(c.startswith(("psql", "pg_restore")) for c in calls)
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
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": FULL, "FAKE_DOCKER_REPLAY_CHECK_EXIT": "1"},
        input_text="0.1.1\n",
    )
    assert result.returncode == 0, result.stderr
    banner = (
        "previous release cannot replay deletions; re-delete these by hand after the "
        f"rollback: account:{ACCOUNT}, chat_session:{CHAT}"
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
        extra_env={"FAKE_DOCKER_DELETIONS_OUT": FULL, "FAKE_DOCKER_REPLAY_CHECK_EXIT": "1"},
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
    result = _rollback(harness, "--yes", extra_env={"FAKE_DOCKER_REPLAY_CHECK_EXIT": "1"})
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
    assert "--since 2027-01-02T03:04:05+00:00" in export
