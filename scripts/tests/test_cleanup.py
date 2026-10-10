# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

"""normly-cleanup: the daily retention run on the VM."""

from pathlib import Path

SYSTEMD = Path(__file__).parents[2] / "deploy" / "systemd"


def test_cleanup_runs_the_pipeline_command(harness):
    result = harness.run("normly-cleanup")
    assert result.returncode == 0, result.stderr
    calls = harness.calls()
    assert len(calls) == 1
    assert calls[0] == "docker compose run --rm --no-deps -T pipeline cleanup-user-data"


def test_cleanup_passes_the_exit_code_through(harness):
    result = harness.run("normly-cleanup", extra_env={"FAKE_DOCKER_EXIT": "7"})
    assert result.returncode == 7


def test_cleanup_defaults_to_the_current_release_compose_file(harness):
    result = harness.run("normly-cleanup", extra_env={"NORMLY_COMPOSE": None})
    assert result.returncode == 0, result.stderr
    expected = (
        f"docker compose -f {harness.dir}/current/compose.yaml "
        f"--project-directory {harness.dir}/current run --rm --no-deps -T pipeline cleanup-user-data"
    )
    assert harness.calls() == [expected]


def test_cleanup_takes_no_arguments(harness):
    result = harness.run("normly-cleanup", "--bogus")
    assert result.returncode == 2
    assert harness.calls() == []


def test_cleanup_service_and_timer():
    service = (SYSTEMD / "normly-cleanup.service").read_text()
    timer = (SYSTEMD / "normly-cleanup.timer").read_text()
    assert "Type=oneshot" in service
    assert "ExecStart=/opt/normly/bin/normly-cleanup" in service
    assert "OnCalendar=*-*-* 04:00:00 UTC" in timer
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer
