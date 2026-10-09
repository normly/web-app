# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import json
from datetime import datetime, timedelta, timezone


def stamp(delta):
    return (datetime.now(timezone.utc) - delta).strftime("%Y%m%dT%H%M%SZ")


def lsf(*names):
    return "\n".join(names)


def deletes(harness):
    return [c.split()[-1].rsplit("/", 1)[-1] for c in harness.calls() if c.startswith("rclone deletefile")]

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
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "TMPDIR": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.glob("normly-backup.*"))


def test_run_rejects_unknown_kind(harness):
    result = harness.run("normly-backup", "run", "--kind", "weekly")
    assert result.returncode == 2


def test_run_rejects_kind_with_path_characters(harness):
    result = harness.run("normly-backup", "run", "--kind", "pre-a/b")
    assert result.returncode == 2
    assert harness.calls() == []


def test_run_aborts_when_table_lookup_fails(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_EXIT": "1"},
    )
    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert not any(c.startswith("pg_dump") for c in harness.calls())


def test_run_failing_encryption_leaves_nothing(harness, tmp_path):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_AGE_EXIT": "1", "TMPDIR": str(tmp_path)},
    )
    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert not list(tmp_path.glob("normly-backup.*"))
    assert not any(c.startswith("rclone") for c in harness.calls())


def test_meta_json_is_valid_json_for_multiline_kb_version(harness, tmp_path):
    keep = tmp_path / "uploaded"
    keep.mkdir()
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={
            "FAKE_DOCKER_OUT": 'account\nsecond "quoted" line',
            "FAKE_RCLONE_KEEP_DIR": str(keep),
        },
    )
    assert result.returncode == 0, result.stderr
    meta = json.loads(next(keep.glob("*.meta.json")).read_text())
    assert "second" in meta["kb_version"] and "\n" in meta["kb_version"]


def test_upload_order_puts_commit_marker_last(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account"},
    )
    assert result.returncode == 0, result.stderr
    uploads = [c.split()[-1] for c in harness.calls() if c.startswith("rclone copyto")]
    assert [u.rsplit(".", 1)[-1] for u in uploads] == ["json", "age", "sha256"]


def test_failed_marker_upload_fails_run_with_no_output(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_RCLONE_FAIL_ON": ".sha256"},
    )
    assert result.returncode != 0
    assert result.stdout.strip() == ""
    uploads = [c for c in harness.calls() if c.startswith("rclone copyto")]
    assert len(uploads) == 3 and uploads[-1].endswith(".sha256")  # marker attempted last


def committed(base):
    return [f"{base}.dump.age", f"{base}.meta.json", f"{base}.sha256"]


def test_prune_deletes_marker_first_then_siblings(harness):
    bases = [f"2026100{d}T100000Z-pre-0.1.{d}" for d in range(1, 5)]
    listing = lsf(*[n for b in bases for n in committed(b)])
    result = harness.run("normly-backup", "prune", extra_env={"FAKE_RCLONE_OUT": listing})
    assert result.returncode == 0, result.stderr
    assert deletes(harness) == [
        "20261001T100000Z-pre-0.1.1.sha256",
        "20261001T100000Z-pre-0.1.1.meta.json",
        "20261001T100000Z-pre-0.1.1.dump.age",
    ]
    assert "pruned 20261001T100000Z-pre-0.1.1" in result.stderr


def test_prune_listing_failure_deletes_nothing(harness):
    result = harness.run("normly-backup", "prune", extra_env={"FAKE_RCLONE_EXIT": "1"})
    assert result.returncode != 0
    assert deletes(harness) == []


def test_prune_ignores_uncommitted_dump_when_counting_backups(harness):
    # 3 committed pre dumps + a newer one without marker: nothing may be deleted,
    # the orphan must not displace a complete backup (it is young, so it stays).
    young = stamp(timedelta(hours=1))
    bases = [f"2026100{d}T100000Z-pre-0.1.{d}" for d in range(1, 4)]
    listing = lsf(*[n for b in bases for n in committed(b)], f"{young}-pre-0.1.9.dump.age")
    result = harness.run("normly-backup", "prune", extra_env={"FAKE_RCLONE_OUT": listing})
    assert result.returncode == 0, result.stderr
    assert deletes(harness) == []


def test_prune_removes_old_orphans_and_keeps_young_ones(harness):
    old = stamp(timedelta(days=2))
    young = stamp(timedelta(hours=2))
    listing = lsf(
        f"{old}-daily.dump.age", f"{old}-daily.meta.json",
        f"{young}-daily.dump.age", f"{young}-daily.meta.json",
        *committed("20261001T033000Z-daily"),
    )
    result = harness.run("normly-backup", "prune", extra_env={"FAKE_RCLONE_OUT": listing})
    assert result.returncode == 0, result.stderr
    assert sorted(deletes(harness)) == [f"{old}-daily.dump.age", f"{old}-daily.meta.json"]


def test_prune_logs_failed_delete_truthfully_and_still_succeeds(harness):
    bases = [f"2026100{d}T100000Z-pre-0.1.{d}" for d in range(1, 5)]
    listing = lsf(*[n for b in bases for n in committed(b)])
    result = harness.run(
        "normly-backup", "prune",
        extra_env={"FAKE_RCLONE_OUT": listing, "FAKE_RCLONE_FAIL_ON": "deletefile"},
    )
    assert result.returncode == 0
    assert "pruned 20261001T100000Z-pre-0.1.1" not in result.stderr
    assert "failed to delete" in result.stderr


def test_failed_dump_upload_never_uploads_the_marker(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_RCLONE_FAIL_ON": ".dump.age"},
    )
    assert result.returncode != 0
    assert not any(c.startswith("rclone copyto") and c.endswith(".sha256") for c in harness.calls())
