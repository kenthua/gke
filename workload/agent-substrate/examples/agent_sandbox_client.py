"""Agent Substrate Actor Sandbox Client for AI Agents.

This module provides a clean Python interface for AI agents (Google GenAI, ADK,
LangChain, AutoGen, CrewAI) to create, manage, and invoke isolated MicroVM
actors on Agent Substrate with sub-second restore latency and automatic cleanup.

Example usage:
    from agent_sandbox_client import ActorSandbox

    # Create and run in an isolated MicroVM sandbox
    with ActorSandbox(template="microvm-actor-template") as sandbox:
        response = sandbox.get("/")
        print(response.text)
"""

import logging
import os
from pathlib import Path
import socket
import subprocess
import time
from typing import Any, Dict, Optional
import urllib.request
import urllib.error

logger = logging.getLogger("agent_sandbox")


def load_dotenv() -> None:
    """Loads environment variables from the repository root .env file if present."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


load_dotenv()


def _find_free_port() -> int:
    """Finds an available local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class ActorSandbox:
    """Manages the lifecycle of an Agent Substrate Actor sandbox."""

    def __init__(
        self,
        template: str = "microvm-actor-template",
        atespace: str = "default",
        name: Optional[str] = None,
        container_port: int = 8080,
        auto_delete: bool = True,
    ):
        self.template = template
        self.atespace = atespace
        self.name = name or f"agent-actor-{int(time.time() * 1000) % 1000000}"
        self.container_port = container_port
        self.auto_delete = auto_delete
        self.local_port = _find_free_port()
        self.proxy_proc: Optional[subprocess.Popen] = None
        self._is_running = False

    def __enter__(self) -> "ActorSandbox":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def actor_exists(self) -> bool:
        """Returns True if this actor already exists in the atespace (Running or Suspended)."""
        res = self._run_ate_cmd(
            ["get", "actor", self.name, "-a", self.atespace], check=False
        )
        return res.returncode == 0

    def start(self) -> None:
        """Creates (if needed) and resumes the actor, then opens a proxy tunnel."""
        if self.actor_exists():
            logger.info(
                f"Actor '{self.name}' already exists in atespace '{self.atespace}'; reusing stateful actor..."
            )
        else:
            logger.info(f"Creating actor '{self.name}' from template '{self.template}'...")
            self._run_ate_cmd(
                ["create", "actor", self.name, "-a", self.atespace, "--template", self.template]
            )

        logger.info(f"Resuming actor '{self.name}' into MicroVM sandbox...")
        t0 = time.perf_counter()
        self._run_ate_cmd(["resume", "actor", self.name, "-a", self.atespace])
        resume_latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"Actor resumed in {resume_latency_ms:.1f}ms")
        self._is_running = True

        self._start_proxy()

    def _start_proxy(self) -> None:
        """Starts a background port proxy to the actor."""
        cmd = [
            "kubectl", "ate", "proxy", "actor", self.name,
            f"{self.local_port}:{self.container_port}",
            "-a", self.atespace
        ]
        self.proxy_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # Wait for the proxy socket to be ready
        base_url = f"http://127.0.0.1:{self.local_port}/"
        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(base_url, timeout=0.5):
                    return
            except urllib.error.HTTPError:
                # Any HTTP status code (e.g. 404 on FastAPI /) confirms the tunnel is live
                return
            except (urllib.error.URLError, ConnectionRefusedError, socket.timeout):
                time.sleep(0.1)
        logger.warning("Proxy tunnel started, but initial probe timed out.")

    def get(self, path: str = "/") -> Dict[str, Any]:
        """Sends an HTTP GET request to the actor sandbox."""
        url = f"http://127.0.0.1:{self.local_port}{path}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            return {
                "status_code": response.status,
                "text": response.read().decode("utf-8"),
                "headers": dict(response.headers),
            }

    def post(self, path: str = "/", json_data: Optional[bytes] = None, timeout: int = 60) -> Dict[str, Any]:
        """Sends an HTTP POST request to the actor sandbox."""
        url = f"http://127.0.0.1:{self.local_port}{path}"
        headers = {"Content-Type": "application/json"} if json_data else {}
        req = urllib.request.Request(url, data=json_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {
                "status_code": response.status,
                "text": response.read().decode("utf-8"),
                "headers": dict(response.headers),
            }

    def suspend(self) -> None:
        """Suspends the actor to save CPU and RAM back to cluster storage."""
        if not self._is_running:
            return
        self._stop_proxy()
        t0 = time.perf_counter()
        self._run_ate_cmd(["suspend", "actor", self.name, "-a", self.atespace])
        suspend_latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"Actor suspended to memory snapshot in {suspend_latency_ms:.1f}ms")
        self._is_running = False

    def resume(self) -> None:
        """Resumes an existing suspended actor from snapshot."""
        if self._is_running:
            return
        t0 = time.perf_counter()
        self._run_ate_cmd(["resume", "actor", self.name, "-a", self.atespace])
        resume_latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"Actor resumed in {resume_latency_ms:.1f}ms")
        self._is_running = True
        self._start_proxy()

    def revert(self) -> None:
        """Reverts the actor to its latest golden snapshot."""
        self._run_ate_cmd(["revert", "actor", self.name, "-a", self.atespace])
        logger.info(f"Actor '{self.name}' reverted to clean snapshot.")

    def close(self) -> None:
        """Stops proxy and tears down the actor."""
        self._stop_proxy()
        if self.auto_delete:
            self._run_ate_cmd(
                ["delete", "actor", self.name, "-a", self.atespace], check=False
            )
            logger.info(f"Deleted actor '{self.name}'.")
        else:
            self.suspend()

    def _stop_proxy(self) -> None:
        if self.proxy_proc and self.proxy_proc.poll() is None:
            self.proxy_proc.terminate()
            try:
                self.proxy_proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.proxy_proc.kill()
            self.proxy_proc = None

    def _run_ate_cmd(self, args: list, check: bool = True) -> subprocess.CompletedProcess:
        full_cmd = ["kubectl", "ate"]
        if os.environ.get("ATE_API_ENDPOINT"):
            full_cmd += ["--endpoint", os.environ["ATE_API_ENDPOINT"]]
        if os.environ.get("ATE_TOKEN_FILE"):
            full_cmd += ["--token-file", os.environ["ATE_TOKEN_FILE"]]
        full_cmd += args
        res = subprocess.run(full_cmd, capture_output=True, text=True)
        if check and res.returncode != 0:
            raise RuntimeError(f"Command {' '.join(full_cmd)} failed:\n{res.stderr}")
        return res


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=== Testing Agent Substrate Actor Sandbox Client ===")
    with ActorSandbox(template="microvm-actor-template") as sandbox:
        print(f"Actor started on local proxy port {sandbox.local_port}")
        res = sandbox.get("/")
        print(f"Status Code: {res['status_code']}")
        print(f"Body:\n{res['text']}")

        print("\nTesting Suspend & Resume Cycle...")
        sandbox.suspend()
        time.sleep(1)
        sandbox.resume()
        res2 = sandbox.get("/")
        print(f"Resumed response:\n{res2['text']}")
    print("=== Done ===")
