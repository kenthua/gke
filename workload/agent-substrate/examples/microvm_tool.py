"""Reusable Google ADK Tool and Lifecycle Callbacks for GKE MicroVM Actors.

This module encapsulates all Agent Substrate actor lifecycle management,
port proxying, and session mapping into a clean, drop-in ADK tool and callback.

Usage:
    from google.adk.agents import Agent
    from microvm_tool import MicroVMSandbox

    sandbox = MicroVMSandbox(template="microvm-actor-template")

    agent = Agent(
        name="coding_agent",
        model="gemini-3.8-flash",
        instruction="Execute commands in the hardware-isolated microvm sandbox.",
        tools=[sandbox.execute],
        after_agent_callback=sandbox.auto_suspend_callback,  # Auto-freezes compute when idle
    )
"""

import json
import logging
import os
import sys
from typing import Any, Dict, Optional
from google.adk.tools import ToolContext
from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

# Add examples dir to path for ActorSandbox
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_sandbox_client import ActorSandbox

logger = logging.getLogger("microvm_tool")


class MicroVMSandbox:
    """Production-grade ADK integration for Agent Substrate MicroVM Actors."""

    def __init__(self, template: str = "microvm-actor-template", atespace: str = "default"):
        self.template = template
        self.atespace = atespace
        self._instances: Dict[str, ActorSandbox] = {}

    def _get_or_resume(self, session_id: str) -> ActorSandbox:
        if session_id not in self._instances:
            actor_name = f"adk-{session_id.replace('-', '')[:8]}"
            logger.info(f"Session [{session_id}]: Spawning MicroVM actor '{actor_name}'...")
            sb = ActorSandbox(template=self.template, atespace=self.atespace, name=actor_name, auto_delete=False)
            sb.start()
            self._instances[session_id] = sb
            return sb

        sb = self._instances[session_id]
        if not sb._is_running:
            logger.info(f"Session [{session_id}]: Waking suspended MicroVM actor '{sb.name}'...")
            sb.resume()
        return sb

    def execute(self, endpoint_or_path: str, tool_context: ToolContext) -> dict:
        """Executes a request inside the hardware-isolated MicroVM actor sandbox.

        Args:
            endpoint_or_path: The HTTP path or endpoint inside the sandbox (e.g. '/' or '/healthz').

        Returns:
            dict containing status_code, output text, and sandbox metadata.
        """
        session_id = tool_context.session.id if tool_context.session else "default"
        sandbox = self._get_or_resume(session_id)
        res = sandbox.get(endpoint_or_path)
        return {
            "status_code": res["status_code"],
            "output": res["text"].strip(),
            "actor": sandbox.name,
            "isolation": "Hardware Cloud Hypervisor MicroVM",
        }

    def run_python(self, code: str, tool_context: ToolContext) -> dict:
        """Executes stateful Python code inside the hardware-isolated MicroVM actor sandbox.

        Variables and state defined in `code` persist in memory across turns even after
        the MicroVM is suspended and resumed from its GCS memory snapshot.

        Args:
            code: Python source code to execute inside the sandbox.

        Returns:
            dict containing stdout, stderr, exit_code, and actor metadata.
        """
        session_id = tool_context.session.id if tool_context.session else "default"
        sandbox = self._get_or_resume(session_id)
        payload = json.dumps({"code": code}).encode("utf-8")
        res = sandbox.post("/execute", json_data=payload)
        data = json.loads(res["text"])
        return {
            "stdout": data.get("stdout", ""),
            "stderr": data.get("stderr", ""),
            "exit_code": data.get("exit_code", 0),
            "actor": sandbox.name,
            "isolation": "Hardware Cloud Hypervisor MicroVM",
        }

    async def auto_suspend_callback(self, ctx: CallbackContext) -> Optional[genai_types.Content]:
        """ADK lifecycle callback: Automatically suspends the MicroVM when the agent turn completes.

        Frees 100% of CPU and RAM on the GKE node during user think-time while retaining
        in-memory snapshot state for instant resumption on the next turn.
        """
        session_id = ctx.session.id if ctx.session else "default"
        if session_id in self._instances and self._instances[session_id]._is_running:
            logger.info(f"Auto-suspending MicroVM for session [{session_id}] to save cluster resources...")
            self._instances[session_id].suspend()
        return None

    def cleanup(self, session_id: Optional[str] = None) -> None:
        """Deletes the MicroVM actor(s)."""
        targets = [session_id] if session_id and session_id in self._instances else list(self._instances.keys())
        for sid in targets:
            sb = self._instances.pop(sid, None)
            if sb:
                sb.auto_delete = True
                sb.close()
