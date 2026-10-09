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


def test_meta_json_takes_the_last_line_of_the_kb_version_and_escapes_quotes(harness, tmp_path):
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
    assert meta["kb_version"] == 'second "quoted" line'


def test_upload_order_puts_commit_marker_last(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account"},
    )
    assert result.returncode == 0, result.stderr
    uploads = [c.split()[-1] for c in harness.calls() if c.startswith("rclone copyto")]
    assert [u.rsplit(".", 1)[-1] for u in uploads] == ["json", "age", "age", "sha256"]
    assert [u.rsplit("/", 1)[-1].split(".", 1)[1] for u in uploads] == [
        "meta.json", "dump.age", "tombstones.age", "sha256",
    ]


def test_failed_marker_upload_fails_run_with_no_output(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_RCLONE_FAIL_ON": ".sha256"},
    )
    assert result.returncode != 0
    assert result.stdout.strip() == ""
    uploads = [c for c in harness.calls() if c.startswith("rclone copyto")]
    assert len(uploads) == 4 and uploads[-1].endswith(".sha256")  # marker attempted last


def _aborted_without_upload(harness, result):
    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert not any(c.startswith("rclone") for c in harness.calls())


def test_run_aborts_when_revision_lookup_fails(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_PSQL_EXIT": "1"},
    )
    _aborted_without_upload(harness, result)
    assert "Alembic revision" in result.stderr


def test_run_aborts_when_revision_is_empty(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_PSQL_OUT": ""},
    )
    _aborted_without_upload(harness, result)


def test_run_aborts_when_kb_info_fails(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_DOCKER_FAIL_ON": "exchange info"},
    )
    _aborted_without_upload(harness, result)
    assert "knowledge-base version" in result.stderr


def test_run_aborts_when_kb_info_prints_nothing(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_DOCKER_INFO_EMPTY": "1"},
    )
    _aborted_without_upload(harness, result)


def test_run_accepts_kb_info_none_and_records_revision(harness, tmp_path):
    keep = tmp_path / "uploaded"
    keep.mkdir()
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_DOCKER_INFO_OUT": "none",
                   "FAKE_RCLONE_KEEP_DIR": str(keep)},
    )
    assert result.returncode == 0, result.stderr
    meta = json.loads(next(keep.glob("*.meta.json")).read_text())
    assert meta["alembic_revision"] == "rev0001"
    assert meta["kb_version"] == "none"


def test_prune_invalid_date_orphan_does_not_stop_pruning(harness):
    old = stamp(timedelta(days=2))
    listing = lsf(
        "20261399T250000Z-daily.dump.age",  # matches the stamp shape, not a real date
        f"{old}-daily.dump.age",
    )
    result = harness.run("normly-backup", "prune", extra_env={"FAKE_RCLONE_OUT": listing})
    assert result.returncode == 0, result.stderr
    assert deletes(harness) == [f"{old}-daily.dump.age"]
    assert "invalid timestamp" in result.stderr


def committed(base):
    return [f"{base}.dump.age", f"{base}.tombstones.age", f"{base}.meta.json", f"{base}.sha256"]


def test_prune_deletes_marker_first_then_siblings(harness):
    bases = [f"2026100{d}T100000Z-pre-0.1.{d}" for d in range(1, 5)]
    listing = lsf(*[n for b in bases for n in committed(b)])
    result = harness.run("normly-backup", "prune", extra_env={"FAKE_RCLONE_OUT": listing})
    assert result.returncode == 0, result.stderr
    assert deletes(harness) == [
        "20261001T100000Z-pre-0.1.1.sha256",
        "20261001T100000Z-pre-0.1.1.meta.json",
        "20261001T100000Z-pre-0.1.1.tombstones.age",
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
        f"{old}-daily.dump.age", f"{old}-daily.meta.json", f"{old}-daily.tombstones.age",
        f"{young}-daily.dump.age", f"{young}-daily.meta.json", f"{young}-daily.tombstones.age",
        *committed("20261001T033000Z-daily"),
    )
    result = harness.run("normly-backup", "prune", extra_env={"FAKE_RCLONE_OUT": listing})
    assert result.returncode == 0, result.stderr
    assert sorted(deletes(harness)) == [
        f"{old}-daily.dump.age", f"{old}-daily.meta.json", f"{old}-daily.tombstones.age",
    ]


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


def test_run_exports_tombstones_in_the_container_after_the_dump_and_encrypts_them(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily", extra_env={"FAKE_DOCKER_OUT": "account"}
    )
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    dump = next(i for i, c in enumerate(calls) if c.startswith("pg_dump"))
    dump_age = next(i for i, c in enumerate(calls) if c.startswith("age ") and ".dump.age" in c)
    export = next(i for i, c in enumerate(calls) if "exchange export-tombstones" in c)
    tomb_age = next(i for i, c in enumerate(calls) if c.startswith("age ") and "tombstones.age" in c)
    assert dump < dump_age < export < tomb_age
    assert "run --rm --no-deps -T --entrypoint python pipeline" in calls[export]
    assert "-r age1recipient" in calls[tomb_age]


def test_checksum_file_covers_both_encrypted_files(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily", extra_env={"FAKE_DOCKER_OUT": "account"}
    )
    assert result.returncode == 0, result.stderr
    sums = next(c for c in harness.calls() if c.startswith("sha256sum"))
    assert ".dump.age" in sums and ".tombstones.age" in sums


def test_meta_json_flags_the_tombstone_file(harness, tmp_path):
    keep = tmp_path / "uploaded"
    keep.mkdir()
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_RCLONE_KEEP_DIR": str(keep)},
    )
    assert result.returncode == 0, result.stderr
    meta = json.loads(next(keep.glob("*.meta.json")).read_text())
    assert meta["tombstones"] is True


def test_run_aborts_without_upload_or_plaintext_when_tombstone_export_fails(harness, tmp_path):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_DOCKER_FAIL_ON": "export-tombstones",
                   "TMPDIR": str(tmp_path)},
    )
    _aborted_without_upload(harness, result)
    assert "tombstone" in result.stderr
    assert not list(tmp_path.glob("normly-backup.*"))


def test_tombstone_encryption_failure_aborts_without_upload(harness, tmp_path):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_AGE_FAIL_ON": "tombstones",
                   "TMPDIR": str(tmp_path)},
    )
    _aborted_without_upload(harness, result)
    assert not list(tmp_path.glob("normly-backup.*"))


def test_failed_tombstone_upload_never_uploads_the_marker(harness):
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_RCLONE_FAIL_ON": ".tombstones.age"},
    )
    assert result.returncode != 0
    assert not any(c.startswith("rclone copyto") and c.endswith(".sha256") for c in harness.calls())


def test_prune_removes_an_orphaned_tombstone_file_and_keeps_a_young_one(harness):
    old = stamp(timedelta(days=2))
    young = stamp(timedelta(hours=2))
    listing = lsf(f"{old}-daily.tombstones.age", f"{young}-daily.tombstones.age")
    result = harness.run("normly-backup", "prune", extra_env={"FAKE_RCLONE_OUT": listing})
    assert result.returncode == 0, result.stderr
    assert deletes(harness) == [f"{old}-daily.tombstones.age"]


def test_run_aborts_when_the_tombstone_export_is_empty_or_malformed(harness, tmp_path):
    for bad in ("", "not json", '{"format": 1, "rows": {"work": []}}'):
        result = harness.run(
            "normly-backup", "run", "--kind", "daily",
            extra_env={"FAKE_DOCKER_OUT": "account", "FAKE_DOCKER_TOMBSTONES_OUT": bad,
                       "TMPDIR": str(tmp_path)},
        )
        _aborted_without_upload(harness, result)
        assert "tombstone export is invalid" in result.stderr
        assert not any("tombstones.age" in c for c in harness.calls() if c.startswith("age "))
        assert not list(tmp_path.glob("normly-backup.*"))


def test_prune_does_not_log_a_failure_for_objects_an_old_backup_never_had(harness):
    bases = [f"2026100{d}T100000Z-pre-0.1.{d}" for d in range(1, 5)]
    old = [f"{bases[0]}.dump.age", f"{bases[0]}.meta.json", f"{bases[0]}.sha256"]
    listing = lsf(*old, *[n for b in bases[1:] for n in committed(b)])
    result = harness.run(
        "normly-backup", "prune",
        extra_env={"FAKE_RCLONE_OUT": listing, "FAKE_RCLONE_FAIL_ON": f"{bases[0]}.tombstones.age"},
    )
    assert result.returncode == 0, result.stderr
    assert deletes(harness) == [f"{bases[0]}.sha256", f"{bases[0]}.meta.json", f"{bases[0]}.dump.age"]
    assert "failed to delete" not in result.stderr
    assert f"pruned {bases[0]}" in result.stderr


def test_prune_still_deletes_with_a_listing_larger_than_the_pipe_buffer(harness):
    # The looked-up object sits at the START of a >64 KiB listing: a
    # `printf | grep -q` pipeline dies of SIGPIPE (141) under pipefail.
    bases = [f"2026100{d}T100000Z-pre-0.1.{d}" for d in range(1, 5)]
    padding = [f"padding-{i:05d}-{'x' * 30}" for i in range(2000)]
    listing = lsf(*[n for b in bases for n in committed(b)], *padding)
    assert len(listing) > 65536
    result = harness.run("normly-backup", "prune", extra_env={"FAKE_RCLONE_OUT": listing})
    assert result.returncode == 0, result.stderr
    assert len(deletes(harness)) == 4
    assert "failed to delete" not in result.stderr
