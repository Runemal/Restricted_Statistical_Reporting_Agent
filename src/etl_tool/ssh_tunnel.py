from __future__ import annotations

import subprocess
import socket
import time
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType

from .config import SshConfig


class SshTunnel(AbstractContextManager["SshTunnel"]):
    def __init__(self, config: SshConfig):
        self.config = config
        self.process: subprocess.Popen[str] | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.config.local_host}:{self.config.local_port}"

    def __enter__(self) -> "SshTunnel":
        command = [
            "ssh",
            "-N",
            "-L",
            (
                f"{self.config.local_host}:{self.config.local_port}:"
                f"{self.config.remote_host}:{self.config.remote_port}"
            ),
            "-p",
            str(self.config.port),
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={self.config.connect_timeout_seconds}",
        ]
        if self.config.identity_file:
            command.extend(["-i", str(Path(self.config.identity_file).expanduser())])
        command.append(self.config.target)

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + self.config.connect_timeout_seconds
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                raise RuntimeError(f"SSH tunnel failed: {stderr.strip()}")
            if _port_is_open(self.config.local_host, self.config.local_port):
                return self
            time.sleep(0.2)
        raise RuntimeError("Timed out waiting for SSH tunnel")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        return False


def _port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False
