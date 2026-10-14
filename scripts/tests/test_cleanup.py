# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""normly-cleanup: the daily retention run on the VM."""

from pathlib import Path

SYSTEMD = Path(__file__).parents[2] / "deploy" / "systemd"


def test_cleanup_runs_the_pipeline_command(harness):
    harness.set_current_tag()
    result = harness.run("normly-cleanup")
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    assert len(calls) == 1
    assert calls[0] == "docker compose run --rm --no-deps -T pipeline cleanup-user-data"


def test_cleanup_passes_the_exit_code_through(harness):
    harness.set_current_tag()
    result = harness.run("normly-cleanup", extra_env={"FAKE_DOCKER_EXIT": "7"})
    assert result.returncode == 7


def test_cleanup_defaults_to_the_current_release_compose_file(harness):
    harness.set_current_tag()
    result = harness.run("normly-cleanup", extra_env={"NORMLY_COMPOSE": None})
    assert result.returncode == 0, result.stderr
    expected = (
        f"docker compose -f {harness.dir}/current/compose.yaml "
        f"--project-directory {harness.dir}/current run --rm --no-deps -T pipeline cleanup-user-data"
    )
    assert harness.calls() == [expected]


def test_cleanup_pins_the_running_release_tag(harness):
    harness.set_current_tag("0.4.2")
    result = harness.run("normly-cleanup", extra_env={"NORMLY_IMAGE_TAG": "edge"})
    assert result.returncode == 0, result.stderr
    assert harness.tags() == ["0.4.2"]


def test_cleanup_without_a_current_tag_runs_nothing(harness):
    for content in (None, "\n"):
        if content is not None:
            harness.set_current_tag("")
        result = harness.run("normly-cleanup")
        assert result.returncode == 1
        assert "current_tag" in result.stderr
    assert harness.calls() == []


def test_cleanup_takes_no_arguments(harness):
    result = harness.run("normly-cleanup", "--bogus")
    assert result.returncode == 2
    assert harness.calls() == []


def test_cleanup_is_skipped_while_a_deploy_or_rollback_holds_the_lock(harness):
    (harness.dir / "state" / "deploy.lock").mkdir(parents=True)
    result = harness.run("normly-cleanup")
    assert result.returncode == 0
    assert "deploy.lock" in result.stderr
    assert harness.calls() == []


def test_cleanup_runs_when_no_lock_exists(harness):
    harness.set_current_tag()
    assert harness.run("normly-cleanup").returncode == 0
    assert len(harness.calls()) == 1


def test_cleanup_service_and_timer():
    service = (SYSTEMD / "normly-cleanup.service").read_text()
    timer = (SYSTEMD / "normly-cleanup.timer").read_text()
    assert "Type=oneshot" in service
    assert "ExecStart=/opt/normly/bin/normly-cleanup" in service
    assert "OnCalendar=*-*-* 04:00:00 UTC" in timer
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer
