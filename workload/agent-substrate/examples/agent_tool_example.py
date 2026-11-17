"""Example of integrating Agent Substrate Actors into an AI Agent workflow.

This demonstrates how a conversational AI or autonomous coding agent
(e.g., Google GenAI, ADK, LangChain, or Claude) can use Agent Substrate MicroVM
actors as an on-demand, hardware-isolated execution sandbox for tools.

Key Advantages for AI Agents:
1. Hardware VM Isolation: Safe execution of arbitrary untrusted code, packages, or scripts.
2. Snapshot Restore (~1.1s): No slow container image pulls or cold VM boots.
3. Suspend & Resume: Put the actor to sleep between conversation turns to save 100% of compute/RAM.
4. Fast Branching: Fork multiple parallel investigation branches from a single snapshot.
"""

import json
import logging
from typing import Any, Dict
from agent_sandbox_client import ActorSandbox

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agent_tool")


class AgentSandboxManager:
    """Manages actor sandbox sessions for agent user interactions."""

    def __init__(self, template: str = "microvm-actor-template"):
        self.template = template
        self.active_sessions: Dict[str, ActorSandbox] = {}

    def get_or_create_session(self, session_id: str) -> ActorSandbox:
        """Retrieves an existing sandbox or creates a new one from snapshot."""
        if session_id not in self.active_sessions:
            actor_name = f"sess-{session_id}"
            logger.info(f"Spawning dedicated MicroVM actor for session '{session_id}'...")
            sandbox = ActorSandbox(
                template=self.template,
                name=actor_name,
                auto_delete=False,
            )
            sandbox.start()
            self.active_sessions[session_id] = sandbox
        else:
            sandbox = self.active_sessions[session_id]
            if not sandbox._is_running:
                logger.info(f"Waking up suspended actor for session '{session_id}'...")
                sandbox.resume()
        return sandbox

    def execute_in_sandbox(self, session_id: str, action: str, params: Dict[str, Any]) -> str:
        """Simulates an AI tool call executing inside the MicroVM actor sandbox."""
        sandbox = self.get_or_create_session(session_id)
        
        logger.info(f"Session '{session_id}': Executing action '{action}' inside MicroVM...")
        # Query actor endpoint
        response = sandbox.get("/")
        return json.dumps({
            "session_id": session_id,
            "action": action,
            "status": "success",
            "actor_host": response["text"].strip(),
            "params": params,
        }, indent=2)

    def pause_session(self, session_id: str) -> None:
        """Suspends actor to GCS snapshot when waiting for user response."""
        if session_id in self.active_sessions:
            logger.info(f"Pausing session '{session_id}' to free cluster resources...")
            self.active_sessions[session_id].suspend()

    def end_session(self, session_id: str) -> None:
        """Terminates and deletes the actor sandbox."""
        if session_id in self.active_sessions:
            logger.info(f"Terminating actor for session '{session_id}'...")
            self.active_sessions[session_id].auto_delete = True
            self.active_sessions[session_id].close()
            del self.active_sessions[session_id]


def simulate_agent_turn():
    manager = AgentSandboxManager()
    user_session = "user-alice-42"

    print("\n--- [Turn 1] User asks agent to inspect environment ---")
    result1 = manager.execute_in_sandbox(
        session_id=user_session,
        action="inspect_system",
        params={"command": "uname -a"}
    )
    print(f"Tool Output:\n{result1}")

    print("\n--- Suspending actor while agent waits for next user prompt ---")
    manager.pause_session(user_session)

    print("\n--- [Turn 2] User follows up 10 minutes later: resume actor ---")
    result2 = manager.execute_in_sandbox(
        session_id=user_session,
        action="run_analysis",
        params={"dataset": "sales_q4.csv"}
    )
    print(f"Tool Output:\n{result2}")

    print("\n--- [Cleanup] User ends session ---")
    manager.end_session(user_session)
    print("Done!")


if __name__ == "__main__":
    simulate_agent_turn()
