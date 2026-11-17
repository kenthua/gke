"""Google ADK Agent with Agent Substrate MicroVM Sandbox Integration.

This example demonstrates how an AI Agent built with Google Agent Development Kit (ADK)
can trigger, interact with, and lifecycle-manage hardware-isolated MicroVM actors deployed
on Google Kubernetes Engine (GKE) via Agent Substrate (ATE).

Key Features Demonstrated:
1. Google ADK Agent (`google.adk.agents.Agent`) with custom function tools.
2. Hardware-Isolated MicroVM Sandboxing: Run untrusted workloads or stateful tools safely.
3. Turn-Level Suspend/Resume: Save 100% of compute/RAM between conversational turns by
   suspending microVM memory to cluster snapshot storage (~1.3s) and resuming on-demand (~1.4s).
4. Automated Session-to-Actor Mapping: Ties an ADK session ID to an isolated microVM actor.
5. End-to-End Multi-Turn Execution: Runs through an interactive conversation using `InMemoryRunner`.
"""

import asyncio
import logging
import os
import sys
from typing import Any, Dict, Optional

# Ensure the example directory is in sys.path to import ActorSandbox (which loads root .env)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from agent_sandbox_client import ActorSandbox

# Automatically configure Vertex AI authentication for Gemini models if not explicitly set
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", os.environ.get("PROJECT_ID", "YOUR_PROJECT_ID"))
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools import ToolContext
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("adk_sandbox_example")


class SubstrateSessionManager:
    """Manages MicroVM Actor lifecycles mapped to ADK conversation sessions."""

    def __init__(self, template: str = "microvm-actor-template", atespace: str = "default"):
        self.template = template
        self.atespace = atespace
        self._actors: Dict[str, ActorSandbox] = {}

    def get_or_resume_actor(self, session_id: str) -> ActorSandbox:
        """Retrieves an existing sandbox or creates/resumes one from snapshot."""
        if session_id not in self._actors:
            # Deterministic, clean actor name per session
            clean_id = session_id.replace("-", "")[:8]
            actor_name = f"adk-actor-{clean_id}"
            logger.info(f"ADK Session [{session_id}]: Creating MicroVM actor '{actor_name}' from template '{self.template}'...")
            sandbox = ActorSandbox(
                template=self.template,
                atespace=self.atespace,
                name=actor_name,
                auto_delete=False,
            )
            sandbox.start()
            self._actors[session_id] = sandbox
            return sandbox

        sandbox = self._actors[session_id]
        if not sandbox._is_running:
            logger.info(f"ADK Session [{session_id}]: Resuming suspended MicroVM actor '{sandbox.name}' from snapshot...")
            sandbox.resume()
        return sandbox

    def suspend_actor(self, session_id: str) -> Dict[str, Any]:
        """Suspends the session's actor to persistent cluster storage."""
        sandbox = self._actors.get(session_id)
        if not sandbox:
            return {"status": "error", "message": f"No active actor found for session {session_id}"}
        if not sandbox._is_running:
            return {"status": "noop", "message": f"Actor '{sandbox.name}' is already suspended."}

        logger.info(f"ADK Session [{session_id}]: Suspending MicroVM actor '{sandbox.name}'...")
        sandbox.suspend()
        return {
            "status": "suspended",
            "actor_name": sandbox.name,
            "message": "Actor memory successfully saved to snapshot storage. Compute/RAM released to cluster.",
        }

    def get_status(self, session_id: str) -> Dict[str, Any]:
        """Returns the current state of the actor sandbox for this session."""
        sandbox = self._actors.get(session_id)
        if not sandbox:
            return {"exists": False, "status": "not_created"}
        return {
            "exists": True,
            "actor_name": sandbox.name,
            "status": "Running" if sandbox._is_running else "Suspended",
            "proxy_port": sandbox.local_port if sandbox._is_running else None,
            "template": sandbox.template,
        }

    def cleanup_all(self) -> None:
        """Tears down all actors created during this process."""
        for session_id, sandbox in list(self._actors.items()):
            try:
                logger.info(f"Tearing down actor '{sandbox.name}'...")
                sandbox.auto_delete = True
                sandbox.close()
            except Exception as e:
                logger.warning(f"Error cleaning up actor {sandbox.name}: {e}")
        self._actors.clear()


# Global manager instance used by ADK tool functions
_session_manager = SubstrateSessionManager()


# ---------------------------------------------------------------------------
# ADK Tool Definitions
# ---------------------------------------------------------------------------
def query_microvm_sandbox(
    path: str,
    tool_context: ToolContext,
) -> dict:
    """Queries an isolated MicroVM actor running on GKE Agent Substrate via HTTP.

    If the actor is suspended or not yet created for this session, it will be
    automatically created or restored from its memory snapshot (~1.4s).

    Args:
        path: The HTTP path or endpoint inside the sandbox (e.g., '/' or '/healthz').

    Returns:
        dict containing HTTP status_code, body text, and actor details.
    """
    session_id = tool_context.session.id if tool_context.session else "default-session"
    sandbox = _session_manager.get_or_resume_actor(session_id)

    try:
        res = sandbox.get(path=path)
        return {
            "status": "success",
            "actor_name": sandbox.name,
            "http_status": res["status_code"],
            "response_body": res["text"].strip(),
            "note": "Executed inside hardware-isolated MicroVM on GKE.",
        }
    except Exception as e:
        return {
            "status": "error",
            "actor_name": sandbox.name,
            "error_message": str(e),
        }


def suspend_microvm_sandbox(tool_context: ToolContext) -> dict:
    """Suspends the session's MicroVM actor into persistent snapshot storage.

    Call this tool when finished with a task or when waiting for user input.
    Suspension vacates CPU and RAM from the GKE node, saving 100% of compute costs
    while retaining full memory state for instant resumption when the user returns.

    Returns:
        dict containing the suspension confirmation and actor name.
    """
    session_id = tool_context.session.id if tool_context.session else "default-session"
    return _session_manager.suspend_actor(session_id)


def get_sandbox_status(tool_context: ToolContext) -> dict:
    """Checks the lifecycle status of the session's MicroVM actor sandbox.

    Returns:
        dict with exists (bool), actor_name, status ('Running' or 'Suspended'), and template.
    """
    session_id = tool_context.session.id if tool_context.session else "default-session"
    return _session_manager.get_status(session_id)


# ---------------------------------------------------------------------------
# ADK Agent Definition
# ---------------------------------------------------------------------------
def create_microvm_agent(model_name: str = "gemini-3.8-flash") -> Agent:
    """Creates the root ADK Agent equipped with MicroVM sandbox management tools."""
    return Agent(
        name="microvm_operator",
        model=model_name,
        instruction="""You are an intelligent DevOps and Sandbox Execution Agent with access to hardware-isolated MicroVM actors running on Google Kubernetes Engine (GKE) via Agent Substrate (ATE).

Your capabilities:
1. `query_microvm_sandbox`: Use this to run workloads or inspect endpoints inside the isolated MicroVM sandbox. If the actor is sleeping/suspended, calling this tool wakes it up automatically.
2. `get_sandbox_status`: Use this to verify whether the microVM actor is Running, Suspended, or Not Created.
3. `suspend_microvm_sandbox`: Use this whenever the user asks to pause, sleep, or save resources, or after completing a task before waiting for user review. Suspending saves cluster compute while preserving state.

Guidelines:
- Explain what actions you are performing clearly.
- Highlight the microVM execution environment, isolation benefits, and suspend/resume latency when relevant.
""",
        tools=[query_microvm_sandbox, get_sandbox_status, suspend_microvm_sandbox],
    )


# ---------------------------------------------------------------------------
# Multi-Turn Interactive Execution Runner
# ---------------------------------------------------------------------------
async def run_turn(runner: InMemoryRunner, user_id: str, session_id: str, user_prompt: str) -> None:
    """Executes a single conversational turn in the ADK agent session."""
    print(f"\n💬 USER: \"{user_prompt}\"")
    msg = types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)])

    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=msg):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(f"  🔧 [Tool Call] {part.function_call.name}({part.function_call.args})")
                elif part.function_response:
                    print(f"  📥 [Tool Response] {part.function_response.response}")
                elif part.text:
                    print(f"🤖 AGENT: {part.text}")


async def main():
    print("=" * 70)
    print("  Google ADK Agent + GKE Agent Substrate MicroVM Sandbox Demo")
    print("=" * 70)

    agent = create_microvm_agent()
    runner = InMemoryRunner(agent=agent)

    user_id = "developer-1"
    session = await runner.session_service.create_session(
        user_id=user_id, app_name=runner.app_name
    )
    session_id = session.id
    print(f"Initialized ADK Session: {session_id}")

    try:
        # Turn 1: Inspect environment and trigger microVM creation / query
        print("\n" + "=" * 50)
        print("TURN 1: Triggering MicroVM Sandbox from ADK Agent")
        print("=" * 50)
        await run_turn(
            runner,
            user_id,
            session_id,
            "Please check the sandbox status, query the root endpoint of the microVM actor, and report what environment is running.",
        )

        # Turn 2: Suspend actor to demonstrate turn-level cost savings
        print("\n" + "=" * 50)
        print("TURN 2: Turn-Level Suspend (Save Compute Resources)")
        print("=" * 50)
        await run_turn(
            runner,
            user_id,
            session_id,
            "I'm going to step away for a bit. Please suspend the microvm actor so we don't consume CPU or memory while waiting.",
        )

        # Turn 3: Resume actor on-demand when user returns
        print("\n" + "=" * 50)
        print("TURN 3: On-Demand Resume from Snapshot")
        print("=" * 50)
        await run_turn(
            runner,
            user_id,
            session_id,
            "I'm back! Please wake up the sandbox, query it again to confirm it's healthy, and show me the status.",
        )

    finally:
        print("\n" + "=" * 50)
        print("CLEANUP: Tearing down temporary demo actors")
        print("=" * 50)
        _session_manager.cleanup_all()
        print("Teardown complete.")


if __name__ == "__main__":
    asyncio.run(main())
