"""Tests for spystroke.autostart: boot registration on all platforms."""

import sys
from pathlib import Path

import pytest

from spystroke.autostart import (
    autostart_installed,
    install_autostart,
    uninstall_autostart,
)


@pytest.fixture
def fake_home(tmp_path):
    return tmp_path / "home"


@pytest.fixture
def fake_root(tmp_path):
    return tmp_path / "repo"


@pytest.fixture
def fake_python(tmp_path):
    """python.exe with a sibling pythonw.exe (like a real Windows install)."""
    exe = tmp_path / "bin" / "python.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("", encoding="utf-8")
    (tmp_path / "bin" / "pythonw.exe").write_text("", encoding="utf-8")
    return exe


class _Recorder:
    """Records commands instead of running them."""

    def __init__(self):
        self.commands = []

    def __call__(self, command):
        self.commands.append(command)


def _install(platform, fake_home, fake_root, fake_python, appdata=None):
    recorder = _Recorder()
    target = install_autostart(
        "telegram",
        platform=platform,
        home=fake_home,
        appdata=appdata,
        root=fake_root,
        python_exe=fake_python,
        run=recorder,
    )
    return target, recorder


class TestWindows:
    def test_writes_vbs_launcher(self, fake_home, fake_root, fake_python):
        appdata = str(fake_home / "AppData" / "Roaming")
        target, recorder = _install(
            "win32", fake_home, fake_root, fake_python, appdata=appdata
        )
        assert target.name == "spystroke-telegram.vbs"
        assert target.exists()

        content = target.read_text(encoding="utf-8")
        # Uses pythonw (no console) and runs the supervisor hidden.
        assert "pythonw.exe" in content
        assert "spystroke.supervisor run telegram" in content
        assert str(fake_root) in content
        # No system commands on Windows.
        assert recorder.commands == []

    def test_falls_back_to_python_when_no_pythonw(
        self, fake_home, fake_root, fake_python
    ):
        # Remove pythonw.exe: the launcher must fall back to python.exe.
        fake_python.with_name("pythonw.exe").unlink()
        appdata = str(fake_home / "AppData" / "Roaming")
        target, _ = _install(
            "win32", fake_home, fake_root, fake_python, appdata=appdata
        )
        content = target.read_text(encoding="utf-8")
        assert "pythonw.exe" not in content
        assert "python.exe" in content

    def test_installed_and_uninstall(self, fake_home, fake_root, fake_python):
        appdata = str(fake_home / "AppData" / "Roaming")
        install_autostart(
            "telegram",
            platform="win32",
            home=fake_home,
            appdata=appdata,
            root=fake_root,
            python_exe=fake_python,
            run=_Recorder(),
        )
        assert autostart_installed(
            "telegram", platform="win32", home=fake_home, appdata=appdata
        )
        assert uninstall_autostart(
            "telegram", platform="win32", home=fake_home, appdata=appdata
        )
        assert not autostart_installed(
            "telegram", platform="win32", home=fake_home, appdata=appdata
        )


class TestLinux:
    def test_writes_systemd_unit_and_enables(self, fake_home, fake_root, fake_python):
        target, recorder = _install("linux", fake_home, fake_root, fake_python)
        assert target.name == "spystroke-telegram.service"
        assert target.parent == fake_home / ".config" / "systemd" / "user"

        content = target.read_text(encoding="utf-8")
        assert f"ExecStart={fake_python} -m spystroke.supervisor run telegram" in content
        assert f"WorkingDirectory={fake_root}" in content
        assert "Restart=always" in content

        # systemctl daemon-reload, enable --now, and linger best-effort.
        assert recorder.commands[0][:3] == ["systemctl", "--user", "daemon-reload"]
        assert recorder.commands[1][:5] == [
            "systemctl", "--user", "enable", "--now", "spystroke-telegram.service",
        ]

    def test_uninstall_disables_and_removes(self, fake_home, fake_root, fake_python):
        recorder = _Recorder()
        install_autostart(
            "email",
            platform="linux",
            home=fake_home,
            root=fake_root,
            python_exe=fake_python,
            run=recorder,
        )
        assert uninstall_autostart(
            "email", platform="linux", home=fake_home, run=recorder
        )
        assert recorder.commands[-1][:4] == [
            "systemctl", "--user", "disable", "--now",
        ]


class TestMacOS:
    def test_writes_launchd_plist(self, fake_home, fake_root, fake_python):
        target, recorder = _install("darwin", fake_home, fake_root, fake_python)
        assert target.name == "com.spystroke.telegram.plist"
        assert target.parent == fake_home / "Library" / "LaunchAgents"

        content = target.read_text(encoding="utf-8")
        assert "<key>Label</key>" in content
        assert "<string>com.spystroke.telegram</string>" in content
        assert "<key>KeepAlive</key>" in content
        assert "<true/>" in content
        assert str(fake_python) in content

        # LaunchAgent is loaded with launchctl.
        assert recorder.commands[0][:3] == ["launchctl", "load", "-w"]


class TestPlatformSupport:
    def test_unknown_platform_raises(self, fake_home, fake_root, fake_python):
        with pytest.raises(NotImplementedError):
            install_autostart(
                "telegram",
                platform="plan9",
                home=fake_home,
                root=fake_root,
                python_exe=fake_python,
                run=_Recorder(),
            )

    def test_uninstall_missing_registration_returns_false(
        self, fake_home, fake_root, fake_python
    ):
        assert not uninstall_autostart(
            "telegram", platform="linux", home=fake_home, run=_Recorder()
        )
