"""Ongoing Stateful Conversation Client for Pattern 3 (ADK Agent IS the ActorTemplate).

Because `ActorSandbox` is configured with `auto_delete=False`:
- When this script finishes, `adk-user-alice` is **SUSPENDED** (not deleted), saving
  its entire Python heap (`InMemorySessionService`) and `/tmp/workspace` filesystem to
  a Cloud Storage memory snapshot while consuming 0 CPU and 0 RAM.
- Every time you run this script again (or pass a new prompt on the CLI), it wakes
  `adk-user-alice` from her latest snapshot and continues `session-1` right where she left off!

Usage:
  # Run 1: Initial two-turn demo (leaves 'adk-user-alice' suspended in GCS at the end)
  python3 examples/adk_actor_template/client_demo.py

  # Run 2+: Resume Alice's ongoing conversation from a completely new process!
  python3 examples/adk_actor_template/client_demo.py "What files are in my workspace and what did we do earlier?"

  # Optional: Delete Alice's actor when completely done
  python3 examples/adk_actor_template/client_demo.py --delete
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import urllib.error

examples_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if examples_dir not in sys.path:
    sys.path.insert(0, examples_dir)

from agent_sandbox_client import ActorSandbox

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("adk_actor_client")


def configure_actor_egress_and_auth(sandbox: ActorSandbox) -> None:
    """Attaches the *.googleapis.com EgressPolicy and pushes a fresh short-lived ADC token."""
    egress_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "egress-policy.yaml")
    subprocess.run(
        [
            "kubectl",
            "ate",
            "create",
            "egress-policy",
            sandbox.name,
            "-a",
            sandbox.atespace,
            "-f",
            egress_file,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
    # Use a short expires_in (5s) so google-auth inside the MicroVM always re-reads
    # the freshly injected token from the local metadata bridge after waking from a snapshot
    # (since the guest VM clock pauses while suspended in GCS).
    sandbox.post(
        "/auth/token",
        json_data=json.dumps({"access_token": token, "expires_in": 5}).encode("utf-8"),
    )


def ensure_session(sandbox: ActorSandbox, user_id: str, session_id: str) -> None:
    """Checks if the ADK session already exists in the restored MicroVM memory; creates it if not."""
    path = f"/apps/app/users/{user_id}/sessions/{session_id}"
    try:
        res = sandbox.get(path)
        session_data = json.loads(res["text"])
        num_events = len(session_data.get("events", []))
        logger.info(
            f"Restored existing ADK session '{session_id}' from MicroVM RAM "
            f"({num_events} prior conversation events in memory)."
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.info(f"Creating new ADK session '{session_id}' for user '{user_id}'...")
            sandbox.post(path, json_data=b"{}")
        else:
            raise


def send_adk_turn(sandbox: ActorSandbox, user_id: str, session_id: str, text: str) -> list:
    """Sends a user message to the ADK `/run` endpoint running inside the MicroVM Actor."""
    print(f"\nUSER ({user_id}): {text}")
    payload = json.dumps({
        "appName": "app",
        "userId": user_id,
        "sessionId": session_id,
        "newMessage": {
            "role": "user",
            "parts": [{"text": text}],
        },
    }).encode("utf-8")
    res = sandbox.post("/run", json_data=payload)
    events = json.loads(res["text"])
    for ev in events:
        for part in ev.get("content", {}).get("parts", []):
            if "functionCall" in part:
                fc = part["functionCall"]
                print(f"  -> [Tool Call inside MicroVM] {fc.get('name')}({fc.get('args')})")
            elif "functionResponse" in part:
                fr = part["functionResponse"]
                print(f"  <- [Tool Response] {fr.get('response')}")
            elif "executableCode" in part:
                print(f"  -> [Code Execution inside MicroVM]\n{part['executableCode'].get('code', '').strip()}")
            elif "codeExecutionResult" in part:
                print(f"  <- [Code Result] {part['codeExecutionResult'].get('output', '').strip()}")
            elif "text" in part and part["text"].strip():
                print(f"Agent Actor: {part['text'].strip()}")
    return events


def main():
    parser = argparse.ArgumentParser(description="Stateful ADK Agent Actor Client")
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Send a follow-up prompt to Alice's ongoing stateful actor session.",
    )
    parser.add_argument("--user", default="alice", help="User ID (default: alice)")
    parser.add_argument("--session", default="session-1", help="Session ID (default: session-1)")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the user's actor instead of suspending it.",
    )
    args = parser.parse_args()

    template = os.environ.get("ADK_ACTOR_TEMPLATE", "adk-agent-actor-template")
    actor_name = f"adk-user-{args.user}"

    if args.delete:
        subprocess.run(["kubectl", "ate", "delete", "actor", actor_name, "-a", "default"], check=False)
        print(f"Deleted actor '{actor_name}'.")
        return

    print(f"=== Connecting to Stateful ADK Agent Actor '{actor_name}' ===")
    # auto_delete=False ensures that exiting the `with` block SUSPENDS the actor to GCS
    # instead of deleting it, so future runs resume from the exact same memory state!
    with ActorSandbox(template=template, name=actor_name, auto_delete=False) as actor:
        configure_actor_egress_and_auth(actor)
        ensure_session(actor, args.user, args.session)

        if args.prompt:
            # Single ongoing turn from CLI argument
            send_adk_turn(actor, args.user, args.session, args.prompt)
        else:
            # Default multi-turn walkthrough
            print("\n[Turn 1] Sending prompt to resident ADK Agent Actor...")
            send_adk_turn(
                actor,
                args.user,
                args.session,
                "Use write_workspace_file to save 'hello from turn 1' into notes.txt and use run_bash to run 'uname -a'.",
            )

            print("\n[Idle] Suspending entire ADK Agent Actor to GCS memory snapshot...")
            actor.suspend()

            print("\n[Turn 2] Resuming ADK Agent Actor from memory snapshot...")
            actor.resume()
            configure_actor_egress_and_auth(actor)
            send_adk_turn(
                actor,
                args.user,
                args.session,
                "Use read_workspace_file to read notes.txt from your workspace and remind me what kernel version we found in Turn 1.",
            )

    print(
        f"\n✓ Actor '{actor_name}' is now SUSPENDED in GCS (0 CPU / 0 RAM).\n"
        f"  Resume Alice's conversation anytime by running:\n"
        f'  python3 examples/adk_actor_template/client_demo.py "What is in notes.txt and what did we discuss?"'
    )


if __name__ == "__main__":
    main()
