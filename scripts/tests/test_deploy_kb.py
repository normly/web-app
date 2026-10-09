# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Rollback preflight for the knowledge-base dump (verify before the drop)."""


def _seed(harness, kb="2026.10.1"):
    state = harness.dir / "state"
    state.mkdir(exist_ok=True)
    (state / "current_tag").write_text("0.1.2\n")
    (state / "previous_tag").write_text("0.1.1\n")
    (state / "pre_rollout_backup").write_text("20261009T100000Z-pre-0.1.2\n")
    (state / "pre_rollout_kb_version").write_text(f"{kb}\n")
    (harness.dir / "releases" / "0.1.1").mkdir(parents=True, exist_ok=True)
    return state


def _rollback(harness, *extra, extra_env=None, input_text=None):
    identity = harness.dir / "age.key"
    identity.write_text("AGE-SECRET-KEY-fake\n")
    return harness.run(
        "normly-deploy", "rollback", "--age-identity", str(identity), *extra,
        extra_env=extra_env, input_text=input_text,
    )


def test_rollback_verifies_the_kb_dump_before_anything_destructive(harness):
    _seed(harness)
    result = _rollback(harness, "--yes")
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    verify = next(i for i, c in enumerate(calls) if "exchange verify --fetch 2026.10.1" in c)
    first_destructive = next(
        i for i, c in enumerate(calls)
        if " down" in c or c.startswith(("psql", "age", "pg_restore"))
    )
    assert verify < first_destructive


def test_rollback_aborts_before_confirmation_when_the_kb_dump_cannot_be_verified(harness):
    state = _seed(harness)
    result = _rollback(  # no --yes: must not even reach the prompt
        harness, extra_env={"FAKE_DOCKER_FAIL_ON": "exchange verify"}, input_text="0.1.1\n"
    )
    assert result.returncode != 0
    assert "2026.10.1 cannot be verified" in result.stderr
    assert "nothing was changed" in result.stderr
    assert "Type the target tag" not in result.stderr
    calls = harness.calls()
    assert not any(" down" in c for c in calls)
    assert not any(c.startswith(("psql", "age", "pg_restore")) for c in calls)
    assert (state / "current_tag").read_text().strip() == "0.1.2"
    assert not (state / "deploy.lock").exists()


def test_rollback_skips_kb_verification_when_no_kb_version_recorded(harness):
    _seed(harness, kb="none")
    assert _rollback(harness, "--yes").returncode == 0
    assert not any("exchange verify" in c for c in harness.calls())


def test_rollback_mounts_the_public_key_for_verify_and_import(harness):
    _seed(harness)
    key = harness.dir / "kb.pub.pem"
    key.write_text("pem\n")
    result = _rollback(harness, "--yes", extra_env={"NORMLY_KB_PUBLIC_KEY_FILE": str(key)})
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    mount = f"-v {key}:/kb-key.pem:ro -e NORMLY_KB_PUBLIC_KEY_FILE=/kb-key.pem"
    verify = next(c for c in calls if "exchange verify" in c)
    imp = next(c for c in calls if "normly_core.exchange import" in c)
    assert mount in verify and mount in imp


def test_rollback_without_key_env_passes_no_mount(harness):
    _seed(harness)
    assert _rollback(harness, "--yes").returncode == 0
    assert not any("kb-key.pem" in c for c in harness.calls())


def test_rollback_refuses_a_missing_key_file_before_anything_destructive(harness):
    _seed(harness)
    result = _rollback(
        harness, "--yes",
        extra_env={"NORMLY_KB_PUBLIC_KEY_FILE": str(harness.dir / "nope.pem")},
    )
    assert result.returncode != 0
    assert "NORMLY_KB_PUBLIC_KEY_FILE" in result.stderr
    assert not any(" down" in c for c in harness.calls())


BACKUP = "20261009T100000Z-pre-0.1.2"
TOMB_LISTING = f"{BACKUP}.tombstones.age"
MARKER_DOC = (
    '{"format": 1, "created_at": "2026-10-09T00:00:00+00:00", "rows": {"source": [], '
    '"delivery": [], "work": [{"marker": "seeded"}], "document": [], "edge": []}}'
)


def test_rollback_restores_tombstones_after_kb_import_and_before_user_data(harness, tmp_path):
    _seed(harness)
    stdin_file = tmp_path / "tombstones-stdin"
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_RCLONE_OUT": TOMB_LISTING, "FAKE_PSQL_OUT": "account",
                   "FAKE_DOCKER_STDIN_FILE": str(stdin_file),
                   "FAKE_RCLONE_TOMBSTONES": MARKER_DOC},
    )
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    drop = next(i for i, c in enumerate(calls) if c.startswith("psql") and "DROP TABLE" in c)
    migrate = next(i for i, c in enumerate(calls) if "migrate" in c)
    kb_import = next(i for i, c in enumerate(calls) if "exchange import --fetch" in c)
    tombs = next(i for i, c in enumerate(calls) if "exchange import-tombstones" in c)
    restore = next(i for i, c in enumerate(calls) if c.startswith("pg_restore"))
    assert drop < migrate < kb_import < tombs < restore
    assert "run --rm --no-deps -T --entrypoint python pipeline" in calls[tombs]
    # the decrypted file arrives on stdin
    assert stdin_file.read_text() == MARKER_DOC
    assert any(c.startswith("age -d") and "tombstones.age" in c for c in calls)
    assert "no tombstone file" not in result.stderr


def test_rollback_without_tombstone_file_warns_before_the_prompt_and_continues(harness):
    _seed(harness)
    result = _rollback(harness, input_text="0.1.1\n")
    assert result.returncode == 0, result.stderr
    assert "backup has no tombstone file" in result.stderr
    assert result.stderr.index("no tombstone file") < result.stderr.index("Type the target tag")
    calls = harness.calls()
    assert not any("import-tombstones" in c for c in calls)
    assert any(c.startswith("pg_restore") for c in calls)


def test_rollback_aborts_before_the_drop_when_the_tombstone_download_fails(harness):
    state = _seed(harness)
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_RCLONE_OUT": TOMB_LISTING, "FAKE_RCLONE_FAIL_ON": "tombstones.age "},
    )
    assert result.returncode != 0
    assert "dropped and is incomplete" not in result.stderr
    calls = harness.calls()
    assert not any(c.startswith(("psql", "pg_restore")) or " down" in c for c in calls)
    assert (state / "current_tag").read_text().strip() == "0.1.2"


def test_rollback_aborts_before_the_drop_when_the_tombstone_listing_fails(harness):
    _seed(harness)
    result = _rollback(
        harness, "--yes", extra_env={"FAKE_RCLONE_FAIL_ON": "lsf"},
    )
    assert result.returncode != 0
    assert not any(c.startswith(("psql", "pg_restore")) for c in harness.calls())


def test_rollback_tombstone_import_failure_prints_recovery_guidance(harness):
    state = _seed(harness)
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_RCLONE_OUT": TOMB_LISTING, "FAKE_DOCKER_FAIL_ON": "import-tombstones"},
    )
    assert result.returncode != 0
    assert "dropped and is incomplete" in result.stderr
    assert "current_tag is still 0.1.2" in result.stderr
    assert not any(c.startswith("pg_restore") for c in harness.calls())
    assert not (state / "deploy.lock").exists()
    assert (state / "current_tag").read_text().strip() == "0.1.2"
    assert (state / "previous_tag").read_text().strip() == "0.1.1"


def test_rollback_leaves_no_decrypted_tombstones_behind(harness, tmp_path):
    _seed(harness)
    result = _rollback(
        harness, "--yes",
        extra_env={"FAKE_RCLONE_OUT": TOMB_LISTING, "TMPDIR": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.glob("normly-rollback.*"))


def test_rollback_aborts_before_anything_destructive_when_the_decrypted_tombstones_are_invalid(harness):
    state = _seed(harness)
    for bad in ("", "not json", '{"format": 2, "rows": {}}',
                '{"format": 1, "rows": {"source": []}}'):
        result = _rollback(
            harness, "--yes",
            extra_env={"FAKE_RCLONE_OUT": TOMB_LISTING, "FAKE_RCLONE_TOMBSTONES": bad},
        )
        assert result.returncode != 0
        assert "is invalid" in result.stderr and "nothing was changed" in result.stderr
        assert "dropped and is incomplete" not in result.stderr
        calls = harness.calls()
        assert not any(c.startswith(("psql", "pg_restore")) or " down" in c for c in calls)
        assert (state / "current_tag").read_text().strip() == "0.1.2"


def test_rollback_invalid_tombstones_abort_before_the_prompt(harness):
    _seed(harness)
    result = _rollback(
        harness, extra_env={"FAKE_RCLONE_OUT": TOMB_LISTING, "FAKE_RCLONE_TOMBSTONES": ""},
        input_text="0.1.1\n",
    )
    assert result.returncode != 0
    assert "Type the target tag" not in result.stderr


def test_rollback_treats_flagged_backup_without_tombstone_object_as_damaged(harness):
    _seed(harness)
    result = _rollback(
        harness, input_text="0.1.1\n",
        extra_env={"FAKE_RCLONE_META": '{"alembic_revision": "rev1", "tombstones": true}'},
    )
    assert result.returncode != 0
    assert "damaged" in result.stderr
    assert "Type the target tag" not in result.stderr
    assert not any(c.startswith(("psql", "pg_restore")) for c in harness.calls())
