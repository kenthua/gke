"""Pattern 3: ADK Agent running INSIDE an Agent Substrate MicroVM ActorTemplate.

Because this ADK Agent process runs inside a dedicated Cloud Hypervisor MicroVM
with `SNAPSHOT_FIDELITY_MEMORY`:
1. The entire ADK runtime (`InMemorySessionService`, loaded libraries, and LLM clients)
   is snapshotted into the Golden Snapshot and restores in ~1.2s.
2. Each user/session gets its own isolated Actor instance whose in-memory session
   history and local `/workspace` files are preserved across `suspend` and `resume`.
3. The agent can safely use local tools (`run_bash`, file I/O) and `UnsafeLocalCodeExecutor`
   because the actor itself is hardware-isolated at the hypervisor level (`/dev/kvm`).
"""

import os
import subprocess
from google.adk.agents import Agent
from google.adk.code_executors import UnsafeLocalCodeExecutor

WORKSPACE_DIR = "/tmp/workspace"
os.makedirs(WORKSPACE_DIR, exist_ok=True)


def run_bash(command: str) -> dict:
    """Executes a shell command inside this actor's isolated MicroVM guest OS.

    Args:
        command: The bash command string to execute.

    Returns:
        dict containing returncode, stdout, and stderr.
    """
    proc = subprocess.run(
        command,
        shell=True,
        cwd=WORKSPACE_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def write_workspace_file(filename: str, content: str) -> dict:
    """Writes a file into the actor's persistent /tmp/workspace directory.

    Args:
        filename: Relative filename inside the workspace.
        content: Text content to write.

    Returns:
        dict confirming the saved file path and byte count.
    """
    path = os.path.join(WORKSPACE_DIR, os.path.basename(filename))
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "saved", "path": path, "bytes": len(content)}


def read_workspace_file(filename: str) -> dict:
    """Reads a file from the actor's persistent /tmp/workspace directory.

    Args:
        filename: Relative filename inside the workspace.

    Returns:
        dict with the file content or error status.
    """
    path = os.path.join(WORKSPACE_DIR, os.path.basename(filename))
    if not os.path.exists(path):
        return {"status": "not_found", "path": path}
    with open(path, "r", encoding="utf-8") as f:
        return {"status": "ok", "path": path, "content": f.read()}


root_agent = Agent(
    name="actor_resident_adk_agent",
    model="gemini-3.8-flash",
    instruction=(
        "You are an autonomous software engineering agent living inside a dedicated "
        "Agent Substrate MicroVM Actor. Your entire memory state, session history, "
        "and `/tmp/workspace` filesystem are snapshotted to GCS when idle and restored "
        "instantly when resumed. Use `run_bash`, `write_workspace_file`, "
        "`read_workspace_file`, or Python code execution to complete tasks."
    ),
    tools=[run_bash, write_workspace_file, read_workspace_file],
    code_executor=UnsafeLocalCodeExecutor(),
)
