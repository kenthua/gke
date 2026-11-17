"""Pattern 2: Google ADK Agent using a custom BaseCodeExecutor on GKE MicroVM Actors.

This example demonstrates how to plug Agent Substrate MicroVM Actors directly into
ADK's `BaseCodeExecutor` interface (`Agent(..., code_executor=...)`).

How it works:
1. Whenever the Gemini model outputs a ```python ... ``` or `executable_code` block,
   ADK automatically intercepts it and invokes `SubstrateMicroVMCodeExecutor.execute_code()`.
2. The executor spawns (or wakes from a GCS memory snapshot in ~1.2s) a session-scoped
   MicroVM actor created from `python-sandbox-template`.
3. The Python code executes inside a persistent in-memory namespace inside the guest VM.
4. At the end of each conversational turn, `after_agent_callback` automatically suspends
   the MicroVM back to GCS (0 CPU / 0 RAM) while preserving all Python variables in RAM!
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Optional

from pydantic import PrivateAttr
from typing_extensions import override

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_sandbox_client import ActorSandbox  # Also loads root .env if present

# Configure Vertex AI / ADC environment (auto-populated from .env if present)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", os.environ.get("PROJECT_ID", "YOUR_PROJECT_ID"))
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.code_executors import BaseCodeExecutor
from google.adk.code_executors.code_execution_utils import (
    CodeExecutionInput,
    CodeExecutionResult,
)
from google.adk.runners import InMemoryRunner
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("adk_code_executor")


class SubstrateMicroVMCodeExecutor(BaseCodeExecutor):
    """Stateful ADK BaseCodeExecutor backed by an Agent Substrate MicroVM Actor."""

    template: str = "python-sandbox-template"
    atespace: str = "default"
    stateful: bool = True

    _actors: Dict[str, ActorSandbox] = PrivateAttr(default_factory=dict)

    def _get_or_resume(self, session_id: str) -> ActorSandbox:
        if session_id not in self._actors:
            actor_name = f"adk-exec-{session_id.replace('-', '')[:8]}"
            logger.info(
                f"Session [{session_id}]: Creating MicroVM code-executor actor '{actor_name}' "
                f"from template '{self.template}'..."
            )
            actor = ActorSandbox(
                template=self.template,
                atespace=self.atespace,
                name=actor_name,
                auto_delete=False,
            )
            actor.start()
            self._actors[session_id] = actor
            return actor

        actor = self._actors[session_id]
        if not actor._is_running:
            logger.info(
                f"Session [{session_id}]: Resuming MicroVM actor '{actor.name}' from memory snapshot..."
            )
            actor.resume()
        return actor

    @override
    def execute_code(
        self,
        invocation_context: InvocationContext,
        code_execution_input: CodeExecutionInput,
    ) -> CodeExecutionResult:
        """Executes LLM-generated Python code blocks inside the MicroVM actor."""
        session_id = (
            invocation_context.session.id if invocation_context.session else "default"
        )
        actor = self._get_or_resume(session_id)

        payload = json.dumps({"code": code_execution_input.code}).encode("utf-8")
        try:
            res = actor.post("/execute", json_data=payload)
            data = json.loads(res["text"])
            return CodeExecutionResult(
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
            )
        except Exception as e:
            logger.error(f"MicroVM code execution error: {e}", exc_info=True)
            return CodeExecutionResult(stderr=str(e))

    async def auto_suspend_callback(
        self, callback_context: CallbackContext
    ) -> Optional[types.Content]:
        """Suspends the MicroVM actor after the agent finishes its turn."""
        session_id = (
            callback_context.session.id if callback_context.session else "default"
        )
        actor = self._actors.get(session_id)
        if actor and actor._is_running:
            logger.info(
                f"Turn complete for session [{session_id}]: Suspending MicroVM '{actor.name}' "
                "to GCS memory snapshot (0 CPU / 0 RAM)..."
            )
            actor.suspend()
        return None

    def cleanup(self, session_id: Optional[str] = None) -> None:
        """Tears down the MicroVM actor(s)."""
        targets = (
            [session_id]
            if session_id and session_id in self._actors
            else list(self._actors.keys())
        )
        for sid in targets:
            actor = self._actors.pop(sid, None)
            if actor:
                actor.auto_delete = True
                actor.close()


# 1. Instantiate the MicroVM CodeExecutor
microvm_executor = SubstrateMicroVMCodeExecutor(template="python-sandbox-template")

# 2. Define the ADK Agent with `code_executor` and automatic turn-level suspension
agent = Agent(
    name="microvm_code_executor_agent",
    model="gemini-3.8-flash",
    instruction=(
        "You are a quantitative Python analyst running code inside a stateful, "
        "hardware-isolated MicroVM actor. Always write Python code inside ```python "
        "code blocks to compute answers. Variables you define in one turn remain "
        "in memory in subsequent turns even after the MicroVM suspends and resumes."
    ),
    code_executor=microvm_executor,
    after_agent_callback=microvm_executor.auto_suspend_callback,
)


async def run_turn(runner: InMemoryRunner, user_id: str, session_id: str, prompt: str) -> None:
    print(f"\nUSER: {prompt}")
    msg = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=msg
    ):
        if event.content and event.content.parts:
            for p in event.content.parts:
                if p.executable_code:
                    print(f"  -> [Executable Code]\n{p.executable_code.code.strip()}")
                elif p.code_execution_result:
                    print(
                        f"  <- [Execution Result ({p.code_execution_result.outcome})]\n"
                        f"     {p.code_execution_result.output.strip()}"
                    )
                elif p.text:
                    print(f"Agent: {p.text.strip()}")


async def main():
    runner = InMemoryRunner(agent=agent)
    session = await runner.session_service.create_session(
        user_id="alice", app_name=runner.app_name
    )

    print(f"=== ADK BaseCodeExecutor + MicroVM Snapshot Demo (Session: {session.id[:8]}) ===")

    try:
        # Turn 1: Define state in Python memory -> auto-suspends to GCS at end of turn
        print("\n[Turn 1] Compute portfolio metrics and store variable in MicroVM RAM:")
        await run_turn(
            runner,
            "alice",
            session.id,
            "Create a Python dictionary named `portfolio` with {'GOOG': 150, 'NVDA': 200, 'MSFT': 100} "
            "and print the total number of shares.",
        )

        # Turn 2: Resumes from GCS memory snapshot -> `portfolio` variable is still in RAM!
        print("\n[Turn 2] Follow-up turn (MicroVM wakes from snapshot with RAM intact):")
        await run_turn(
            runner,
            "alice",
            session.id,
            "Without redefining `portfolio`, read the existing `portfolio` variable from memory, "
            "add 50 shares of 'GOOG', and print the updated dictionary.",
        )
    finally:
        print("\nCleaning up MicroVM code-executor actor...")
        microvm_executor.cleanup(session.id)
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
