# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""Compose-dialect .env handling, release folder safety, empty-KB banner."""

import os
import shutil
import subprocess

from conftest import SCRIPTS

UNSET = {
    "NORMLY_DATABASE_URL": None,
    "NORMLY_BACKUP_AGE_RECIPIENT": None,
    "NORMLY_BACKUP_REMOTE": None,
}

DOTENV = """\
# Compose-style file
COMPOSE_PROFILES=bundled
NORMLY_BRAND_COLOR_HSL=222 89% 55%
NORMLY_BUNDLED_POSTGRES_PASSWORD=pa$$word #not-a-comment-in-bash
SOME_UNKNOWN_KEY=must-not-leak
export NORMLY_DATABASE_URL="postgresql+psycopg://u:p@db:5432/normly"
NORMLY_BACKUP_AGE_RECIPIENT='age1recipient'
NORMLY_BACKUP_REMOTE=stackit:my bucket # trailing comment
RCLONE_CONFIG_STACKIT_TYPE=s3
NORMLY_BACKUP_REMOTE=stackit:my bucket
"""


def _write_env(harness, text=DOTENV):
    (harness.dir / ".env").write_text(text)


def _load(harness, *names, extra_env=None):
    script = (
        f'. "{SCRIPTS}/normly-env.sh"; normly_load_env "{harness.dir}/.env"; '
        + "; ".join(f'printf "%s=[%s]\\n" {n} "${{{n}-UNSET}}"' for n in names)
    )
    env = {"PATH": os.environ["PATH"], **(extra_env or {})}
    out = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return dict(line.split("=", 1) for line in out.stdout.splitlines())


def test_loader_reads_compose_dialect_and_exports_only_needed_keys(harness):
    _write_env(harness)
    got = _load(
        harness, "NORMLY_BRAND_COLOR_HSL", "SOME_UNKNOWN_KEY", "NORMLY_BUNDLED_POSTGRES_PASSWORD",
        "NORMLY_DATABASE_URL", "NORMLY_BACKUP_AGE_RECIPIENT", "NORMLY_BACKUP_REMOTE",
        "RCLONE_CONFIG_STACKIT_TYPE",
    )
    assert got["NORMLY_BRAND_COLOR_HSL"] == "[UNSET]"
    assert got["SOME_UNKNOWN_KEY"] == "[UNSET]"
    assert got["NORMLY_BUNDLED_POSTGRES_PASSWORD"] == "[UNSET]"
    assert got["NORMLY_DATABASE_URL"] == "[postgresql+psycopg://u:p@db:5432/normly]"
    assert got["NORMLY_BACKUP_AGE_RECIPIENT"] == "[age1recipient]"
    assert got["NORMLY_BACKUP_REMOTE"] == "[stackit:my bucket]"
    assert got["RCLONE_CONFIG_STACKIT_TYPE"] == "[s3]"


def test_loader_keeps_dollar_and_hash_inside_needed_values(harness):
    _write_env(
        harness,
        'NORMLY_DATABASE_URL=postgresql://u:p$w#x@db/n\n'
        'NORMLY_BACKUP_REMOTE="a #b $HOME `id`"\n',
    )
    got = _load(harness, "NORMLY_DATABASE_URL", "NORMLY_BACKUP_REMOTE")
    assert got["NORMLY_DATABASE_URL"] == "[postgresql://u:p$w#x@db/n]"
    assert got["NORMLY_BACKUP_REMOTE"] == "[a #b $HOME `id`]"


def test_process_environment_wins_over_the_file(harness):
    _write_env(harness, "NORMLY_BACKUP_REMOTE=from-file\n")
    got = _load(harness, "NORMLY_BACKUP_REMOTE", extra_env={"NORMLY_BACKUP_REMOTE": "from-env"})
    assert got["NORMLY_BACKUP_REMOTE"] == "[from-env]"


def test_backup_runs_with_branding_in_env_file_and_keeps_spaces(harness):
    _write_env(harness)
    result = harness.run(
        "normly-backup", "run", "--kind", "daily",
        extra_env={**UNSET, "FAKE_DOCKER_OUT": "account"},
    )
    assert result.returncode == 0, result.stderr
    assert any("stackit:my bucket/backups/" in c for c in harness.calls() if c.startswith("rclone"))


def test_rollback_runs_with_branding_in_env_file(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.2\n")
    (state / "previous_tag").write_text("0.1.1\n")
    (state / "pre_rollout_backup").write_text("20261009T100000Z-pre-0.1.2\n")
    (state / "pre_rollout_kb_version").write_text("2026.10.1\n")
    (harness.dir / "releases" / "0.1.1").mkdir(parents=True)
    _write_env(harness)
    identity = harness.dir / "age.key"
    identity.write_text("k\n")
    result = harness.run(
        "normly-deploy", "rollback", "--age-identity", str(identity), "--yes",
        extra_env=UNSET,
    )
    assert result.returncode == 0, result.stderr
    assert any(c.startswith("pg_restore") for c in harness.calls())


# --- release folder safety ---------------------------------------------------


def test_failed_extraction_keeps_the_existing_release_folder(harness):
    state = harness.dir / "state"
    state.mkdir()
    (state / "current_tag").write_text("0.1.2\n")
    (state / "previous_tag").write_text("0.1.1\n")
    release = harness.dir / "releases" / "0.1.1"
    release.mkdir(parents=True)
    (release / "compose.yaml").write_text("keep\n")
    (harness.dir / "releases" / "0.1.2").mkdir(parents=True)

    result = harness.run(
        "normly-deploy", "deploy", "0.1.1", extra_env={"FAKE_DOCKER_EXIT_ON": "cp"}
    )

    assert result.returncode != 0
    assert (release / "compose.yaml").read_text() == "keep\n"
    assert not (harness.dir / "releases" / "0.1.1.new").exists()


def test_successful_extraction_replaces_the_release_folder(harness):
    release = harness.dir / "releases" / "0.1.2"
    release.mkdir(parents=True)
    (release / "stale").write_text("x")
    assert harness.run("normly-deploy", "deploy", "0.1.2").returncode == 0
    assert not (release / "stale").exists()
    assert (release / "verified-digests").is_file()
    assert not (harness.dir / "releases" / "0.1.2.new").exists()


# --- empty knowledge base banner --------------------------------------------


def test_rollback_warns_when_the_knowledge_base_will_be_empty(harness):
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
        "normly-deploy", "rollback", "--age-identity", str(identity), input_text="no\n"
    )

    assert "the knowledge base will be EMPTY after this rollback" in result.stderr
    assert "only the Flex backup can restore it" in result.stderr
    assert "aborted" in result.stderr  # confirmation is still required


# --- loader fails loudly -----------------------------------------------------


def _run_loader(harness, *, path_env=None):
    script = (
        f'set -euo pipefail; . "{SCRIPTS}/normly-env.sh"; normly_load_env "{harness.dir}/.env"; '
        'echo "rc-continued=[${NORMLY_DATABASE_URL-UNSET}]"'
    )
    env = {"PATH": path_env if path_env is not None else os.environ["PATH"]}
    return subprocess.run(
        [shutil.which("bash"), "-c", script], env=env, capture_output=True, text=True
    )


def test_loader_keeps_the_first_key_after_a_utf8_bom(harness):
    _write_env(harness, "﻿NORMLY_DATABASE_URL=postgresql://u:p@db/n\n")
    got = _load(harness, "NORMLY_DATABASE_URL")
    assert got["NORMLY_DATABASE_URL"] == "[postgresql://u:p@db/n]"


def test_loader_without_python3_fails_with_a_clear_message(harness):
    _write_env(harness, "NORMLY_DATABASE_URL=postgresql://u:p@db/n\n")
    empty = harness.dir / "emptybin"
    empty.mkdir()
    out = _run_loader(harness, path_env=str(empty))
    assert out.returncode != 0
    assert "python3" in out.stderr
    assert "rc-continued" not in out.stdout


def test_loader_with_unreadable_env_file_fails_with_a_clear_message(harness):
    if os.geteuid() == 0:
        import pytest

        pytest.skip("root can read any file")
    _write_env(harness, "NORMLY_DATABASE_URL=postgresql://u:p@db/n\n")
    (harness.dir / ".env").chmod(0)
    out = _run_loader(harness)
    assert out.returncode != 0
    assert ".env" in out.stderr
    assert "rc-continued" not in out.stdout


def test_loader_accepts_a_missing_env_file(harness):
    out = _run_loader(harness)
    assert out.returncode == 0
    assert "rc-continued=[UNSET]" in out.stdout


def test_loader_strips_an_inline_comment_after_a_quoted_value(harness):
    _write_env(
        harness,
        'NORMLY_DATABASE_URL="postgresql://u:p@db/n" # prod\n'
        "NORMLY_BACKUP_REMOTE='a #b'   # note\n",
    )
    got = _load(harness, "NORMLY_DATABASE_URL", "NORMLY_BACKUP_REMOTE")
    assert got["NORMLY_DATABASE_URL"] == "[postgresql://u:p@db/n]"
    assert got["NORMLY_BACKUP_REMOTE"] == "[a #b]"


def test_extraction_restores_a_release_folder_left_as_old_by_a_crash(harness):
    releases = harness.dir / "releases"
    old = releases / "0.1.1.old"
    old.mkdir(parents=True)
    (old / "compose.yaml").write_text("keep\n")
    (releases / "0.1.1.new").mkdir()

    result = harness.run(
        "normly-deploy", "deploy", "0.1.1", extra_env={"FAKE_DOCKER_EXIT_ON": "cp"}
    )

    assert result.returncode != 0
    assert (releases / "0.1.1" / "compose.yaml").read_text() == "keep\n"
    assert not old.exists()
    assert not (releases / "0.1.1.new").exists()


def test_extraction_discards_stale_old_and_new_next_to_a_release_folder(harness):
    releases = harness.dir / "releases"
    (releases / "0.1.1").mkdir(parents=True)
    (releases / "0.1.1" / "compose.yaml").write_text("current\n")
    (releases / "0.1.1.old").mkdir()
    (releases / "0.1.1.old" / "compose.yaml").write_text("stale\n")
    (releases / "0.1.1.new").mkdir()

    result = harness.run(
        "normly-deploy", "deploy", "0.1.1", extra_env={"FAKE_DOCKER_EXIT_ON": "cp"}
    )

    assert result.returncode != 0
    assert (releases / "0.1.1" / "compose.yaml").read_text() == "current\n"
    assert not (releases / "0.1.1.old").exists()
    assert not (releases / "0.1.1.new").exists()


def test_successful_extraction_leaves_no_old_or_new_folder(harness):
    release = harness.dir / "releases" / "0.1.2"
    release.mkdir(parents=True)
    assert harness.run("normly-deploy", "deploy", "0.1.2").returncode == 0
    assert not (harness.dir / "releases" / "0.1.2.old").exists()
    assert not (harness.dir / "releases" / "0.1.2.new").exists()
