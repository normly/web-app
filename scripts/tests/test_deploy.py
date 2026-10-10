# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import json

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def _index(calls, prefix):
    return next(i for i, c in enumerate(calls) if c.startswith(prefix))


def _seed(harness, current=None, previous=None, kb="2026.10.1", releases=()):
    """Create the state a VM would have; returns the state directory."""
    state = harness.dir / "state"
    state.mkdir(exist_ok=True)
    if current:
        (state / "current_tag").write_text(f"{current}\n")
        (harness.dir / "releases" / current).mkdir(parents=True, exist_ok=True)
    if previous:
        (state / "previous_tag").write_text(f"{previous}\n")
        (harness.dir / "releases" / previous).mkdir(parents=True, exist_ok=True)
        (state / "pre_rollout_backup").write_text("20261009T100000Z-pre-0.1.2\n")
        (state / "pre_rollout_kb_version").write_text(f"{kb}\n")
    for tag in releases:
        (harness.dir / "releases" / tag).mkdir(parents=True, exist_ok=True)
    return state


def _rollback_args(harness, *extra):
    identity = harness.dir / "age.key"
    identity.write_text("AGE-SECRET-KEY-fake\n")
    return ("normly-deploy", "rollback", "--age-identity", str(identity), *extra)


def test_deploy_runs_in_the_specified_order(harness):
    result = harness.run("normly-deploy", "deploy", "v0.1.2")

    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    verify = _index(calls, "cosign verify")
    pull = next(i for i, c in enumerate(calls) if c.startswith("docker") and " pull" in c)
    assert verify < pull
    assert sum(c.startswith("cosign verify") for c in calls) == 5
    assert (harness.dir / "state" / "current_tag").read_text().strip() == "0.1.2"


def test_deploy_aborts_before_any_change_when_signature_fails(harness):
    result = harness.run("normly-deploy", "deploy", "0.1.2", extra_env={"FAKE_COSIGN_EXIT": "1"})

    assert result.returncode != 0
    assert not any("pull" in c or "up -d" in c for c in harness.calls())
    assert not any(c.startswith("docker create") for c in harness.calls())
    assert not (harness.dir / "state" / "current_tag").exists()


def test_deploy_rejects_non_release_tags(harness):
    for tag in ("edge", "latest", "0.1", "main"):
        assert harness.run("normly-deploy", "deploy", tag).returncode == 2
    assert harness.calls() == []


def test_deploy_aborts_when_pre_rollout_backup_fails(harness):
    state = _seed(harness, current="0.1.1")
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2",
        extra_env={"NORMLY_BACKUP_BIN": "/bin/false"},
    )
    assert result.returncode != 0
    assert "pre-rollout backup failed" in result.stderr
    assert not any("pull" in c for c in harness.calls())
    assert (state / "current_tag").read_text().strip() == "0.1.1"


def test_deploy_moves_current_to_previous(harness):
    state = _seed(harness, current="0.1.1")

    assert harness.run("normly-deploy", "deploy", "0.1.2").returncode == 0

    assert (state / "previous_tag").read_text().strip() == "0.1.1"
    assert (state / "current_tag").read_text().strip() == "0.1.2"


def test_failed_health_wait_keeps_current_tag_and_says_how_to_roll_back(harness):
    state = _seed(harness, current="0.1.1")
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2",
        extra_env={"FAKE_DOCKER_EXIT_ON": "up"},
    )
    assert result.returncode != 0
    assert "rollback" in result.stderr
    assert "releases/0.1.2/compose.yaml logs" in result.stderr
    assert (state / "current_tag").read_text().strip() == "0.1.1"


def test_first_deploy_health_failure_does_not_suggest_rollback(harness):
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2", extra_env={"FAKE_DOCKER_EXIT_ON": "up"}
    )
    assert result.returncode != 0
    assert "rollback" not in result.stderr
    assert not (harness.dir / "state" / "failed_rollout").exists()


def test_second_run_is_refused_while_locked(harness):
    (harness.dir / "state" / "deploy.lock").mkdir(parents=True)
    result = harness.run("normly-deploy", "deploy", "0.1.2")
    assert result.returncode == 3
    assert "already running" in result.stderr


def test_rollback_requires_confirmation(harness):
    _seed(harness, current="0.1.2", previous="0.1.1")

    result = harness.run(*_rollback_args(harness), input_text="no\n")

    assert result.returncode == 1
    assert "aborted" in result.stderr
    calls = harness.calls()
    # the read-only deletion_log lookup of the preflight is not a change
    assert not any(
        c.startswith("pg_restore") or (c.startswith("psql") and "to_regclass" not in c)
        for c in calls
    )
    assert not any(" down" in c for c in calls)


def test_rollback_proceeds_when_the_target_tag_is_typed(harness):
    state = _seed(harness, current="0.1.2", previous="0.1.1")

    result = harness.run(*_rollback_args(harness), input_text="0.1.1\n")

    assert result.returncode == 0, result.stderr
    assert any(c.startswith("pg_restore") for c in harness.calls())
    assert (state / "current_tag").read_text().strip() == "0.1.1"


def test_rollback_rebuilds_schema_then_imports_kb_then_restores_users(harness):
    state = _seed(harness, current="0.1.2", previous="0.1.1")

    result = harness.run(*_rollback_args(harness, "--yes"), extra_env={"FAKE_PSQL_OUT": "account"})

    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    drop = next(i for i, c in enumerate(calls) if c.startswith("psql") and "DROP TABLE" in c)
    migrate = next(i for i, c in enumerate(calls) if "migrate" in c)
    kb_import = next(
        i for i, c in enumerate(calls) if "normly_core.exchange" in c and " import" in c
    )
    restore = _index(calls, "pg_restore")
    assert drop < migrate < kb_import < restore
    assert "--data-only" in calls[restore]
    assert (state / "current_tag").read_text().strip() == "0.1.1"


def test_failed_health_wait_makes_current_the_rollback_target(harness):
    state = _seed(harness, current="0.1.1")
    (state / "previous_tag").write_text("0.1.0\n")
    harness.run(
        "normly-deploy", "deploy", "0.1.2", extra_env={"FAKE_DOCKER_EXIT_ON": "up"}
    )
    assert (state / "previous_tag").read_text().strip() == "0.1.1"
    assert (state / "pre_rollout_backup").read_text().strip() == "20261009T100000Z-pre-0.1.2"
    assert not list(state.glob("*.new"))
    assert not (state / "deploy.lock").exists()


def test_lock_is_released_after_success_and_after_abort(harness):
    assert harness.run("normly-deploy", "deploy", "0.1.2").returncode == 0
    assert not (harness.dir / "state" / "deploy.lock").exists()
    failed = harness.run("normly-deploy", "deploy", "0.1.3", extra_env={"FAKE_COSIGN_EXIT": "1"})
    assert failed.returncode != 0
    assert not (harness.dir / "state" / "deploy.lock").exists()


def test_rollback_keeps_lock_held_by_another_run(harness):
    state = _seed(harness, current="0.1.2", previous="0.1.1")
    (state / "deploy.lock").mkdir()
    result = harness.run(*_rollback_args(harness, "--yes"))
    assert result.returncode == 3
    assert (state / "deploy.lock").is_dir()


def test_rollback_drops_tables_without_dropping_the_schema(harness):
    _seed(harness, current="0.1.2", previous="0.1.1")
    harness.run(*_rollback_args(harness, "--yes"), extra_env={"FAKE_PSQL_OUT": "account"})
    psql = next(c for c in harness.calls() if c.startswith("psql") and "DROP" in c)
    assert 'DROP TABLE IF EXISTS "account" CASCADE;' in psql
    assert "DROP SCHEMA" not in psql


def test_rollback_drop_list_comes_from_the_database(harness):
    _seed(harness, current="0.1.2", previous="0.1.1")
    harness.run(
        *_rollback_args(harness, "--yes"),
        extra_env={"FAKE_PSQL_OUT": "account\nadded_by_newer_release\nalembic_version"},
    )
    calls = harness.calls()
    assert any("pg_tables" in c for c in calls if c.startswith("psql"))
    log = "\n".join(calls)  # the multi-statement -c argument spans several log lines
    assert 'DROP TABLE IF EXISTS "added_by_newer_release" CASCADE;' in log
    assert 'DROP TABLE IF EXISTS "alembic_version" CASCADE;' in log
    assert not any("exchange tables" in c for c in calls)


def test_rollback_skips_kb_import_when_no_kb_version_recorded(harness):
    _seed(harness, current="0.1.2", previous="0.1.1", kb="none")
    result = harness.run(*_rollback_args(harness, "--yes"))
    assert result.returncode == 0, result.stderr
    assert not any(" import" in c and "normly_core.exchange" in c for c in harness.calls())
    assert any(c.startswith("pg_restore") for c in harness.calls())


def test_deploy_records_kb_version_of_the_current_release(harness):
    state = _seed(harness, current="0.1.1")
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2", extra_env={"FAKE_DOCKER_INFO_OUT": "2026.11.2"}
    )
    assert result.returncode == 0, result.stderr
    assert (state / "pre_rollout_kb_version").read_text().strip() == "2026.11.2"
    info = next(c for c in harness.calls() if "exchange info" in c)
    assert "releases/0.1.1/compose.yaml" in info


# --- review round 1 ---------------------------------------------------------


def test_refused_runs_and_status_leave_in_flight_state_files_alone(harness):
    state = _seed(harness, current="0.1.1")
    (state / "deploy.lock").mkdir()
    (state / "pre_rollout_backup.new").write_text("inflight\n")
    (state / "pre_rollout_kb_version.new").write_text("2026.10.1\n")

    assert harness.run("normly-deploy", "status").returncode == 0
    assert harness.run("normly-deploy", "deploy", "0.1.2").returncode == 3
    assert harness.run("normly-deploy", "deploy", "0.1.2").returncode == 3

    assert (state / "pre_rollout_backup.new").read_text() == "inflight\n"
    assert (state / "pre_rollout_kb_version.new").read_text() == "2026.10.1\n"
    assert (state / "deploy.lock").is_dir()


def test_failing_kb_info_aborts_before_backup_and_pull(harness):
    state = _seed(harness, current="0.1.1")
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2", extra_env={"FAKE_DOCKER_FAIL_ON": "exchange info"}
    )
    assert result.returncode != 0
    assert "nothing was changed" in result.stderr
    calls = harness.calls()
    assert not any(" pull" in c for c in calls)
    assert not (state / "pre_rollout_backup.new").exists()
    assert (state / "current_tag").read_text().strip() == "0.1.1"


def test_missing_current_release_folder_aborts_before_backup(harness):
    state = _seed(harness)
    (state / "current_tag").write_text("0.1.1\n")
    result = harness.run("normly-deploy", "deploy", "0.1.2")
    assert result.returncode != 0
    assert "0.1.1" in result.stderr
    assert not any(" pull" in c for c in harness.calls())


def test_kb_info_printing_none_is_accepted(harness):
    state = _seed(harness, current="0.1.1")
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2", extra_env={"FAKE_DOCKER_INFO_OUT": "none"}
    )
    assert result.returncode == 0, result.stderr
    assert (state / "pre_rollout_kb_version").read_text().strip() == "none"


def test_rollback_failure_after_drop_prints_recovery_guidance(harness):
    state = _seed(harness, current="0.1.2", previous="0.1.1")
    result = harness.run(
        *_rollback_args(harness, "--yes"), extra_env={"FAKE_PG_RESTORE_EXIT": "1"}
    )
    assert result.returncode != 0
    assert "dropped and is incomplete" in result.stderr
    assert "current_tag is still 0.1.2" in result.stderr
    assert "normly-deploy rollback --age-identity" in result.stderr
    assert not (state / "deploy.lock").exists()
    assert (state / "current_tag").read_text().strip() == "0.1.2"
    assert (state / "previous_tag").read_text().strip() == "0.1.1"


def test_rollback_failure_before_the_drop_has_no_destructive_message(harness):
    _seed(harness, current="0.1.2", previous="0.1.1")
    result = harness.run(*_rollback_args(harness, "--yes"), extra_env={"FAKE_RCLONE_EXIT": "1"})
    assert result.returncode != 0
    assert "dropped and is incomplete" not in result.stderr


def test_rollback_refuses_when_backup_schema_does_not_match_previous_release(harness):
    state = _seed(harness, current="0.1.2", previous="0.1.1")
    result = harness.run(
        *_rollback_args(harness, "--yes"),
        extra_env={"FAKE_RCLONE_META": json.dumps({"alembic_revision": "rev_new"})},
    )
    assert result.returncode != 0
    assert "rev_new" in result.stderr and "rev1" in result.stderr
    calls = harness.calls()
    assert not any(c.startswith(("psql", "pg_restore", "age")) for c in calls)
    assert not any(" down" in c for c in calls)
    assert (state / "current_tag").read_text().strip() == "0.1.2"


def test_rollback_with_matching_schema_revision_proceeds(harness):
    _seed(harness, current="0.1.2", previous="0.1.1")
    result = harness.run(
        *_rollback_args(harness, "--yes"),
        extra_env={
            "FAKE_RCLONE_META": json.dumps({"alembic_revision": "abc123"}),
            "FAKE_DOCKER_HEAD_OUT": "abc123",
        },
    )
    assert result.returncode == 0, result.stderr


def test_deploy_refuses_the_current_tag(harness):
    _seed(harness, current="0.1.2")
    result = harness.run("normly-deploy", "deploy", "0.1.2")
    assert result.returncode == 2
    assert "already the current release" in result.stderr
    assert harness.calls() == []


def test_failed_rollout_blocks_deploy_until_rolled_back(harness):
    state = _seed(harness, current="0.1.1")
    failed = harness.run(
        "normly-deploy", "deploy", "0.1.2", extra_env={"FAKE_DOCKER_EXIT_ON": "up"}
    )
    assert failed.returncode != 0
    assert (state / "failed_rollout").read_text().strip() == "0.1.2"

    blocked = harness.run("normly-deploy", "deploy", "0.1.3")
    assert blocked.returncode == 4
    assert "failed rollout of 0.1.2" in blocked.stderr
    assert "failed_rollout" in blocked.stderr

    rolled = harness.run(*_rollback_args(harness, "--yes"))
    assert rolled.returncode == 0, rolled.stderr
    assert "Rollback 0.1.2 -> 0.1.1" in rolled.stderr
    assert not (state / "failed_rollout").exists()
    assert harness.run("normly-deploy", "deploy", "0.1.3").returncode == 0


def test_cosign_digest_is_used_for_docker_create_after_verification(harness):
    result = harness.run("normly-deploy", "deploy", "0.1.2")
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    create = next(c for c in calls if c.startswith("docker create"))
    assert create.endswith(f"/pipeline@{DIGEST_A}")
    last_verify = max(i for i, c in enumerate(calls) if c.startswith("cosign verify"))
    assert last_verify < _index(calls, "docker create")
    recorded = (harness.dir / "releases" / "0.1.2" / "verified-digests").read_text()
    assert f"pipeline {DIGEST_A}" in recorded and len(recorded.splitlines()) == 5


def test_unparseable_cosign_output_aborts(harness):
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2", extra_env={"FAKE_COSIGN_OUT": "not json"}
    )
    assert result.returncode != 0
    assert not any(c.startswith("docker") for c in harness.calls())


def test_digest_mismatch_after_pull_aborts_before_up(harness):
    state = _seed(harness, current="0.1.1")
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2",
        extra_env={"FAKE_DOCKER_INSPECT_OUT": f'["ghcr.io/normly/web-app/api@{DIGEST_B}"]'},
    )
    assert result.returncode != 0
    assert "verified digest" in result.stderr
    calls = harness.calls()
    assert any(" pull" in c for c in calls)
    assert not any(" up " in c for c in calls)
    assert (state / "current_tag").read_text().strip() == "0.1.1"
