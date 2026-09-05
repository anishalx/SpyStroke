"""Tests for spystroke.supervisor: restart logic, backoff, and stopping."""

import os
import sys
import threading
import time
from pathlib import Path

import pytest

from spystroke.supervisor import DISCLAIMER, Supervisor, main as supervisor_main


@pytest.fixture
def workdir(tmp_path):
    """A temp dir with tiny delays so tests run fast."""
    return tmp_path


# ---------------------------------------------------------------------------
# Consent gate on run/install
# ---------------------------------------------------------------------------


def _non_interactive(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)


def test_main_run_aborts_without_consent_non_interactive(monkeypatch, capsys):
    """A non-interactive run without --yes must abort, never auto-start."""
    _non_interactive(monkeypatch)
    assert supervisor_main(["run", "telegram"]) == 1
    captured = capsys.readouterr()
    assert DISCLAIMER.strip() in captured.out
    assert "consent not confirmed" in captured.err.lower()


def test_main_install_requires_yes_non_interactive(monkeypatch, capsys):
    """install is gated too; --yes is mandatory without a terminal."""
    _non_interactive(monkeypatch)
    assert supervisor_main(["install", "email"]) == 1
    assert "consent not confirmed" in capsys.readouterr().err.lower()


def test_main_install_proceeds_with_yes_non_interactive(monkeypatch, capsys, tmp_path):
    """--yes skips the prompt and the install proceeds."""
    _non_interactive(monkeypatch)
    monkeypatch.setattr(
        "spystroke.supervisor.install_autostart",
        lambda name: tmp_path / f"{name}.service",
    )
    assert supervisor_main(["install", "telegram", "--yes"]) == 0
    captured = capsys.readouterr()
    assert DISCLAIMER.strip() in captured.out  # disclaimer always printed
    assert "Auto-start registered" in captured.out


def test_main_install_consent_denied(monkeypatch, capsys):
    """Typing anything but 'yes' aborts the install."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "nope")
    assert supervisor_main(["install", "telegram"]) == 1
    assert "consent not confirmed" in capsys.readouterr().err.lower()


def test_main_install_consent_granted(monkeypatch, capsys, tmp_path):
    """Typing 'yes' proceeds with the install."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    monkeypatch.setattr(
        "spystroke.supervisor.install_autostart",
        lambda name: tmp_path / f"{name}.service",
    )
    assert supervisor_main(["install", "telegram"]) == 0
    assert "Auto-start registered" in capsys.readouterr().out


def test_main_status_does_not_require_consent(monkeypatch, capsys, tmp_path):
    """status is informational and never gated."""
    _non_interactive(monkeypatch)
    monkeypatch.setattr("spystroke.supervisor.state_dir", lambda: tmp_path)
    monkeypatch.setattr("spystroke.supervisor.autostart_installed", lambda name: False)
    assert supervisor_main(["status"]) == 0
    out = capsys.readouterr().out
    assert "telegram" in out and "email" in out
    assert DISCLAIMER.strip() not in out


def test_default_state_dir_uses_home(tmp_path, monkeypatch):
    """Regression: state_dir param must not shadow the state_dir() function."""
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))
    entry = _write_entry(tmp_path, "import sys; sys.exit(0)\n")
    sup = Supervisor(
        "t",
        entry,
        restart_delay=0.01,
        max_restarts=1,
        install_signal_handlers=False,
        poll_interval=0.01,
    )
    assert sup.state_dir == tmp_path / ".spystroke"
    assert sup.run() == 0


def _write_entry(dirpath: Path, code: str) -> Path:
    entry = dirpath / "entry.py"
    entry.write_text(code, encoding="utf-8")
    return entry


class TestRestartBehaviour:
    def test_restarts_crashed_child_up_to_max(self, tmp_path, caplog):
        entry = _write_entry(tmp_path, "import sys; sys.exit(3)\n")
        sup = Supervisor(
            "t",
            entry,
            state_dir_override=tmp_path / "state",
            restart_delay=0.01,
            max_delay=0.05,
            healthy_uptime=999.0,  # every exit looks like a crash
            max_restarts=2,
            install_signal_handlers=False,
            poll_interval=0.01,
        )
        assert sup.run() == 0
        assert sup.restarts == 2
        # The child's exit code must be reported through the logger.
        assert "Child exited with code 3" in caplog.text

    def test_backoff_grows_on_crash_loop(self, tmp_path):
        entry = _write_entry(tmp_path, "import sys; sys.exit(1)\n")
        sup = Supervisor(
            "t",
            entry,
            state_dir_override=tmp_path / "state",
            restart_delay=0.01,
            max_delay=1.0,
            healthy_uptime=999.0,
            max_restarts=3,
            install_signal_handlers=False,
            poll_interval=0.01,
        )
        sup.run()
        # After 3 quick crashes the delay must have doubled 3 times.
        assert sup._current_delay == pytest.approx(0.01 * 2**3)

    def test_backoff_resets_after_healthy_uptime(self, tmp_path):
        # Child stays alive 0.05s each time; healthy_uptime is lower, so the
        # delay must reset to the initial value instead of growing.
        entry = _write_entry(tmp_path, "import time; time.sleep(0.05)\n")
        sup = Supervisor(
            "t",
            entry,
            state_dir_override=tmp_path / "state",
            restart_delay=0.01,
            max_delay=1.0,
            healthy_uptime=0.01,
            max_restarts=2,
            install_signal_handlers=False,
            poll_interval=0.01,
        )
        sup.run()
        assert sup._current_delay == sup.restart_delay

    def test_backoff_is_capped_at_max_delay(self, tmp_path):
        entry = _write_entry(tmp_path, "import sys; sys.exit(1)\n")
        sup = Supervisor(
            "t",
            entry,
            state_dir_override=tmp_path / "state",
            restart_delay=0.01,
            max_delay=0.03,
            healthy_uptime=999.0,
            max_restarts=4,
            install_signal_handlers=False,
            poll_interval=0.01,
        )
        sup.run()
        assert sup._current_delay <= 0.03

    def test_pid_file_removed_after_run(self, tmp_path):
        entry = _write_entry(tmp_path, "import sys; sys.exit(0)\n")
        sup = Supervisor(
            "t",
            entry,
            state_dir_override=tmp_path / "state",
            restart_delay=0.01,
            max_restarts=1,
            install_signal_handlers=False,
            poll_interval=0.01,
        )
        sup.run()
        assert not sup._pid_file.exists()


class TestStopBehaviour:
    def test_request_stop_terminates_child(self, tmp_path):
        entry = _write_entry(tmp_path, "import time; time.sleep(60)\n")
        sup = Supervisor(
            "t",
            entry,
            state_dir_override=tmp_path / "state",
            restart_delay=0.01,
            install_signal_handlers=False,
            poll_interval=0.01,
        )

        thread = threading.Thread(target=sup.run, daemon=True)
        thread.start()

        # Wait until the child has been spawned.
        deadline = time.monotonic() + 10
        while sup.child is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert sup.child is not None, "child never started"

        sup.request_stop()
        thread.join(timeout=10)
        assert not thread.is_alive(), "supervisor did not stop"
        # The child must have been terminated.
        assert sup.child.poll() is not None

    def test_refuses_second_instance(self, tmp_path):
        entry = _write_entry(tmp_path, "import time; time.sleep(60)\n")
        sup = Supervisor(
            "t",
            entry,
            state_dir_override=tmp_path / "state",
            install_signal_handlers=False,
            poll_interval=0.01,
        )
        # Simulate a live supervisor by pointing the pid file at this process.
        sup._pid_file.parent.mkdir(parents=True, exist_ok=True)
        sup._pid_file.write_text(str(os.getpid()), encoding="utf-8")
        assert sup.run() == 1
        assert sup.restarts == 0
