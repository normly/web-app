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
