# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

def test_run_dumps_only_user_tables_encrypts_and_uploads(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account\nwatchlist"},
    )

    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    dump = next(c for c in calls if c.startswith("pg_dump"))
    assert "--data-only" in dump and "--format=custom" in dump
    assert "--table=public.account" in dump and "--table=public.watchlist" in dump
    assert "postgresql://u:p@db:5432/normly" in dump  # +psycopg driver suffix removed
    assert any(c.startswith("age ") and "-r age1recipient" in c for c in calls)
    assert any(c.startswith("rclone copyto") and "stackit:bucket/backups/" in c for c in calls)
    name = result.stdout.strip().splitlines()[-1]
    assert name.endswith("-daily")


def test_run_fails_and_prints_nothing_when_upload_fails(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_RCLONE_EXIT": "1"},
    )
    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_run_never_leaves_plaintext_dump_behind(harness, tmp_path):
    harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "TMPDIR": str(tmp_path)},
    )
    assert not list(tmp_path.glob("normly-backup.*"))


def test_run_rejects_unknown_kind(harness):
    result = harness.run("normly-backup", "run", "--kind", "weekly")
    assert result.returncode == 2
