"""Minimal, Clean Google ADK Agent leveraging GKE MicroVM Actors.

Notice how concise this is:
1. No boilerplate session management (handled by ADK session IDs).
2. No manual prompt-based suspend/resume logic (handled automatically by ADK's after_agent_callback).
3. The developer only writes standard ADK code.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from microvm_tool import MicroVMSandbox  # Also loads root .env via agent_sandbox_client

# Standard Vertex AI / ADC environment (auto-populated from .env if present)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", os.environ.get("PROJECT_ID", "YOUR_PROJECT_ID"))
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types

# 1. Instantiate the MicroVM Sandbox Tool
sandbox = MicroVMSandbox(template="microvm-actor-template")

# 2. Define the Agent with automatic turn suspension
agent = Agent(
    name="microvm_assistant",
    model="gemini-3.8-flash",
    instruction="You are an assistant with access to a hardware-isolated MicroVM sandbox. Use sandbox.execute to query or run commands inside the sandbox.",
    tools=[sandbox.execute],
    after_agent_callback=sandbox.auto_suspend_callback,  # Auto-freezes compute when turn finishes!
)


async def main():
    runner = InMemoryRunner(agent=agent)
    session = await runner.session_service.create_session(
        user_id="alice", app_name=runner.app_name
    )

    print(f"=== Clean ADK Agent Demo (Session: {session.id[:8]}) ===")

    try:
        # Turn 1: User asks a question -> Actor auto-wakes, runs, then auto-suspends!
        print("\n[Turn 1] User asks to query sandbox:")
        msg = types.Content(role="user", parts=[types.Part.from_text(text="What is running inside the microvm sandbox at /?")])
        async for event in runner.run_async(user_id="alice", session_id=session.id, new_message=msg):
            if event.content and event.content.parts:
                for p in event.content.parts:
                    if p.function_call:
                        print(f"  -> Tool Call: {p.function_call.name}({p.function_call.args})")
                    elif p.function_response:
                        print(f"  <- Tool Response: {p.function_response.response}")
                    elif p.text:
                        print(f"Agent: {p.text.strip()}")

        # Turn 2: User comes back -> Actor wakes up from snapshot in ~1.4s, then auto-suspends again!
        print("\n[Turn 2] User asks a follow-up 5 minutes later:")
        msg2 = types.Content(role="user", parts=[types.Part.from_text(text="Can you re-verify that the microvm is still responding?")])
        async for event in runner.run_async(user_id="alice", session_id=session.id, new_message=msg2):
            if event.content and event.content.parts:
                for p in event.content.parts:
                    if p.function_call:
                        print(f"  -> Tool Call: {p.function_call.name}({p.function_call.args})")
                    elif p.function_response:
                        print(f"  <- Tool Response: {p.function_response.response}")
                    elif p.text:
                        print(f"Agent: {p.text.strip()}")

    finally:
        print("\nCleaning up actor...")
        sandbox.cleanup(session.id)
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
