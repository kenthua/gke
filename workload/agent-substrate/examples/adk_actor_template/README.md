# Pattern 3: The ADK Agent *Is* the `ActorTemplate`

This directory contains a complete, production-verified example where the **Google ADK Agent runtime (`get_fast_api_app`) runs inside an Agent Substrate Cloud Hypervisor MicroVM Actor** with `SNAPSHOT_FIDELITY_MEMORY`.

---

## 1. Architectural Overview

Instead of running the ADK Agent externally and calling a sandbox for individual tool executions, the entire ADK Agent server is packaged as the `ActorTemplate` (`adk-agent-actor-template`).

```text
+-------------------------------------------------------------------------+
| Client / Gateway (client_demo.py)                                       |
|  1. Resumes (or creates) per-user actor: `adk-user-alice` (~1.7s)       |
|  2. Attaches EgressPolicy (*.googleapis.com:443) & short-lived ADC token|
|  3. Calls POST /run via `kubectl ate proxy`                             |
|  4. Suspends `adk-user-alice` to GCS on exit (0 CPU / 0 RAM)            |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| Cloud Hypervisor MicroVM Actor (`adk-user-alice`)                       |
|                                                                         |
|  FastAPI (`server.py` on :8080)                                         |
|  ├── ADK `InMemorySessionService` (persisted in VM RAM snapshot!)       |
|  ├── `root_agent` (`app/agent.py` - gemini-3.8-flash)                   |
|  │    ├── Tools: `run_bash`, `write_workspace_file`, `read_workspace_file`
|  │    └── CodeExecutor: `UnsafeLocalCodeExecutor()` (safe inside VM!)   |
|  ├── `/tmp/workspace` (guest filesystem preserved across snapshots!)    |
|  └── Local Metadata Bridge (`127.0.0.1:18080`, fed via `POST /auth/token`)|
+-------------------------------------------------------------------------+
```

### Why Run the ADK Agent Inside the `ActorTemplate`?
1. **Zero-Database Stateful Sessions:** ADK's `InMemorySessionService` becomes durable across turns and across days because suspending the actor writes the entire Python heap to Cloud Storage (`SNAPSHOT_FIDELITY_MEMORY`).
2. **Safe Local Execution (`UnsafeLocalCodeExecutor` + Bash):** Because each user's ADK agent lives inside its own hardware-isolated guest Linux kernel (`/dev/kvm`), the agent can safely run arbitrary bash commands, install packages, and use `UnsafeLocalCodeExecutor` locally with zero network round-trips between the agent and its workspace.
3. **Zero-Secret Golden Snapshots:** Static GCP credentials are never baked into the container image or golden memory snapshot. Instead, `server.py` runs a lightweight local GCE Metadata Server emulator (`127.0.0.1:18080`), and the caller injects a fresh, short-lived OAuth access token via `POST /auth/token` whenever the actor wakes up.

---

## 2. Files in This Directory

| File | Purpose |
|---|---|
| [`app/agent.py`](app/agent.py) | Defines `root_agent` with `run_bash`, `write_workspace_file`, `read_workspace_file`, and `UnsafeLocalCodeExecutor()`. |
| [`app/__init__.py`](app/__init__.py) | Exports `root_agent` for ADK's `get_fast_api_app()` discovery. |
| [`server.py`](server.py) | FastAPI server entrypoint exposing ADK endpoints (`/run`, `/apps/...`), `/healthz` wakeup probe, and `/auth/token` credential bridge. |
| [`Dockerfile`](Dockerfile) | Container build definition (`python:3.11-slim` + `google-adk`, `fastapi`, `uvicorn`). |
| [`actortemplate-adk-agent.yaml`](actortemplate-adk-agent.yaml) | `ActorTemplate` manifest (`adk-agent-actor-template`) pinned by `@sha256` digest targeting `microvm-pool`. |
| [`egress-policy.yaml`](egress-policy.yaml) | Agent Substrate `EgressPolicy` enabling `tlsPassthrough` to `*.googleapis.com:443` so the actor can reach Vertex AI. |
| [`client_demo.py`](client_demo.py) | Stateful client that creates/resumes `adk-user-alice`, continues her ongoing `session-1` conversation, and suspends the actor on exit. |

---

## 3. Running & Resuming Ongoing Stateful Conversations

The `adk-agent-actor-template` is built and deployed on the cluster (`GOLDEN TAG: 8c4cb935-e50b-42fa-8fd1-8fa876424aca`).

### Step 1: Run the Initial Multi-Turn Demo
```bash
python3 examples/adk_actor_template/client_demo.py
```
* Spawns (or wakes) `adk-user-alice` from the golden memory snapshot in **~1.7s**.
* **Turn 1:** Writes `'hello from turn 1'` to `/tmp/workspace/notes.txt` and runs `uname -a` inside the MicroVM (`Linux actor 6.18.56`).
* **Idle:** Suspends the entire ADK Agent VM to a GCS memory snapshot (`0 CPU / 0 RAM`).
* **Turn 2:** Wakes `adk-user-alice` in **~1.7s**, reads back `/tmp/workspace/notes.txt`, and recalls the kernel version from Turn 1.
* **On Exit:** Because `ActorSandbox` is initialized with `auto_delete=False`, `adk-user-alice` is left in `ACTOR_STATE_SUSPENDED` in GCS.

### Step 2: Resume Alice's Ongoing Conversation Anytime
Because `adk-user-alice` remains suspended in GCS with both her `InMemorySessionService` history and `/tmp/workspace` intact, you can run a new process hours or days later and pass any follow-up prompt:

```bash
python3 examples/adk_actor_template/client_demo.py "What did we write into notes.txt earlier, and what was the kernel version from our very first turn?"
```

**Output:**
```text
=== Connecting to Stateful ADK Agent Actor 'adk-user-alice' ===
[INFO] Actor 'adk-user-alice' already exists in atespace 'default'; reusing stateful actor...
[INFO] Resuming actor 'adk-user-alice' into MicroVM sandbox...
[INFO] Actor resumed in 1740.4ms
[INFO] Restored existing ADK session 'session-1' from MicroVM RAM (8 prior conversation events in memory).
```

You can also target a different user (which automatically provisions a separate isolated MicroVM actor `adk-user-bob`):
```bash
python3 examples/adk_actor_template/client_demo.py --user bob "Create a file bob.txt in my workspace."
```

### Step 3: Delete the Actor When Completely Done
```bash
python3 examples/adk_actor_template/client_demo.py --delete
```

---

## 4. Rebuilding & Updating the Image with Cloud Build

If you modify [`app/agent.py`](app/agent.py) or [`server.py`](server.py):

### 1. Source Environment Variables (from `.env` / `ate-dev-env.sh`)
```bash
source ./ate-dev-env.sh
```

### 2. Build and Push via Cloud Build
```bash
gcloud builds submit examples/adk_actor_template \
  --project="${PROJECT_ID}" \
  --region="${GCE_REGION}" \
  --tag="${ADK_AGENT_IMAGE_REPO}:v1"
```

### 3. Ensure `atelet` Has Pull Access to the Artifact Registry Repo
*(Already configured on `apps` in `us-central1`)*
```bash
gcloud artifacts repositories add-iam-policy-binding apps \
  --location="${GCE_REGION}" \
  --project="${PROJECT_ID}" \
  --member="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/ate-system/sa/atelet" \
  --role="roles/artifactregistry.reader"

gcloud artifacts repositories add-iam-policy-binding apps \
  --location="${GCE_REGION}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:${NODE_SA_EMAIL}" \
  --role="roles/artifactregistry.reader"
```

### 4. Pin the New `@sha256` Digest and Recreate the `ActorTemplate`
Agent Substrate requires container images in `ActorTemplate` to be pinned by `@sha256` digest so snapshots remain immutable:
```bash
export ADK_AGENT_IMAGE_DIGEST=$(gcloud artifacts docker images describe \
  "${ADK_AGENT_IMAGE_REPO}:v1" \
  --format='value(image_summary.digest)')
export ADK_AGENT_IMAGE="${ADK_AGENT_IMAGE_REPO}@${ADK_AGENT_IMAGE_DIGEST}"

# Recreate ActorTemplate substituting ${ADK_AGENT_IMAGE} and ${PROJECT_ID}:
kubectl ate delete actor-template adk-agent-actor-template -a default
envsubst < examples/adk_actor_template/actortemplate-adk-agent.yaml | kubectl ate create actor-template -f -
kubectl ate get actor-templates -a default
```
