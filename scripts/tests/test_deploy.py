# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import pytest


def _index(calls, prefix):
    return next(i for i, c in enumerate(calls) if c.startswith(prefix))


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
    assert not (harness.dir / "state" / "current_tag").exists()


def test_deploy_rejects_non_release_tags(harness):
    for tag in ("edge", "latest", "0.1", "main"):
        assert harness.run("normly-deploy", "deploy", tag).returncode == 2
    assert harness.calls() == []


def test_deploy_aborts_when_pre_rollout_backup_fails(harness):
    (harness.dir / "state").mkdir()
    (harness.dir / "state" / "current_tag").write_text("0.1.1\n")
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2",
        extra_env={"NORMLY_BACKUP_BIN": "/bin/false"},
    )
    assert result.returncode != 0
    assert not any("pull" in c for c in harness.calls())
    assert (harness.dir / "state" / "current_tag").read_text().strip() == "0.1.1"


def test_deploy_moves_current_to_previous(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.1\n")

    assert harness.run("normly-deploy", "deploy", "0.1.2").returncode == 0

    assert (state / "previous_tag").read_text().strip() == "0.1.1"
    assert (state / "current_tag").read_text().strip() == "0.1.2"


def test_failed_health_wait_keeps_current_tag_and_says_how_to_roll_back(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.1\n")
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2",
        extra_env={"FAKE_DOCKER_EXIT_ON": "up"},
    )
    assert result.returncode != 0
    assert "rollback" in result.stderr
    assert (state / "current_tag").read_text().strip() == "0.1.1"


def test_second_run_is_refused_while_locked(harness):
    (harness.dir / "state" / "deploy.lock").mkdir(parents=True)
    result = harness.run("normly-deploy", "deploy", "0.1.2")
    assert result.returncode == 3
    assert "already running" in result.stderr


def test_rollback_requires_confirmation(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.2\n")
    (state / "previous_tag").write_text("0.1.1\n")
    (state / "pre_rollout_backup").write_text("20261009T100000Z-pre-0.1.2\n")
    (state / "pre_rollout_kb_version").write_text("2026.10.1\n")
    identity = harness.dir / "age.key"
    identity.write_text("AGE-SECRET-KEY-fake\n")

    result = harness.run(
        "normly-deploy", "rollback", "--age-identity", str(identity), input_text="no\n"
    )

    assert result.returncode == 1
    assert not any(c.startswith("pg_restore") for c in harness.calls())


def test_rollback_rebuilds_schema_then_imports_kb_then_restores_users(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.2\n")
    (state / "previous_tag").write_text("0.1.1\n")
    (state / "pre_rollout_backup").write_text("20261009T100000Z-pre-0.1.2\n")
    (state / "pre_rollout_kb_version").write_text("2026.10.1\n")
    (harness.dir / "releases" / "0.1.1").mkdir(parents=True)
    identity = harness.dir / "age.key"
    identity.write_text("AGE-SECRET-KEY-fake\n")

    result = harness.run(
        "normly-deploy", "rollback", "--age-identity", str(identity), "--yes",
        extra_env={"FAKE_DOCKER_OUT": "account"},
    )

    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    drop = _index(calls, "psql")
    migrate = next(i for i, c in enumerate(calls) if "migrate" in c)
    kb_import = next(
        i for i, c in enumerate(calls) if "normly_core.exchange" in c and " import" in c
    )
    restore = _index(calls, "pg_restore")
    assert drop < migrate < kb_import < restore
    assert "--data-only" in calls[restore]
    assert (state / "current_tag").read_text().strip() == "0.1.1"


def test_failed_health_wait_makes_current_the_rollback_target(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.1\n")
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
    state = harness.dir / "state"
    (state / "deploy.lock").mkdir(parents=True)
    (state / "current_tag").write_text("0.1.2\n")
    (state / "previous_tag").write_text("0.1.1\n")
    (state / "pre_rollout_backup").write_text("x\n")
    (harness.dir / "releases" / "0.1.1").mkdir(parents=True)
    identity = harness.dir / "age.key"
    identity.write_text("k\n")
    result = harness.run(
        "normly-deploy", "rollback", "--age-identity", str(identity), "--yes"
    )
    assert result.returncode == 3
    assert (state / "deploy.lock").is_dir()


def test_rollback_drops_tables_without_dropping_the_schema(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.2\n")
    (state / "previous_tag").write_text("0.1.1\n")
    (state / "pre_rollout_backup").write_text("20261009T100000Z-pre-0.1.2\n")
    (state / "pre_rollout_kb_version").write_text("2026.10.1\n")
    (harness.dir / "releases" / "0.1.1").mkdir(parents=True)
    identity = harness.dir / "age.key"
    identity.write_text("k\n")
    harness.run(
        "normly-deploy", "rollback", "--age-identity", str(identity), "--yes",
        extra_env={"FAKE_DOCKER_OUT": "account"},
    )
    psql = next(c for c in harness.calls() if c.startswith("psql"))
    assert 'DROP TABLE IF EXISTS "account" CASCADE;' in psql
    assert "DROP SCHEMA" not in psql


def test_rollback_skips_kb_import_when_no_kb_version_recorded(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.2\n")
    (state / "previous_tag").write_text("0.1.1\n")
    (state / "pre_rollout_backup").write_text("20261009T100000Z-pre-0.1.2\n")
    (state / "pre_rollout_kb_version").write_text("none\n")
    (harness.dir / "releases" / "0.1.1").mkdir(parents=True)
    identity = harness.dir / "age.key"
    identity.write_text("k\n")
    result = harness.run(
        "normly-deploy", "rollback", "--age-identity", str(identity), "--yes"
    )
    assert result.returncode == 0, result.stderr
    assert not any(" import" in c and "normly_core.exchange" in c for c in harness.calls())
    assert any(c.startswith("pg_restore") for c in harness.calls())


def test_deploy_records_kb_version_of_the_current_release(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.1\n")
    (harness.dir / "releases" / "0.1.1").mkdir(parents=True)
    result = harness.run(
        "normly-deploy", "deploy", "0.1.2", extra_env={"FAKE_DOCKER_OUT": "2026.10.1"}
    )
    assert result.returncode == 0, result.stderr
    assert (state / "pre_rollout_kb_version").read_text().strip() == "2026.10.1"
    info = next(c for c in harness.calls() if "exchange info" in c)
    assert "releases/0.1.1/compose.yaml" in info

