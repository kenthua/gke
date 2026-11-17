# Agent Substrate: AI Agent Actor Examples & Integration Guide

This directory contains practical examples and client utilities demonstrating how an **AI Agent** (e.g. Gemini, Google ADK, LangChain, Claude, AutoGen) can leverage the **Agent Substrate MicroVM Actors** deployed in your GKE cluster.

> **Environment Note:** All Python scripts in this directory automatically load variables (`GOOGLE_CLOUD_PROJECT`, `PROJECT_ID`, etc.) from the root [`.env`](../.env) file via [`agent_sandbox_client.py`](agent_sandbox_client.py).

---

## 1. Why Use Agent Substrate Actors for AI Agents?

Traditional agent sandboxes rely on spinning up new Kubernetes pods or Docker containers, which suffer from **10–30s cold starts**, security risks with shared kernels, and continuous idle resource consumption.

Agent Substrate MicroVM Actors solve this with:
1. **Hardware-Assisted VM Isolation (`/dev/kvm`)**: Each actor runs inside its own lightweight Cloud Hypervisor VM with a dedicated guest Linux kernel. Untrusted agent-generated code, arbitrary bash scripts, or dependencies cannot compromise the host node or neighbor workloads.
2. **Sub-Second Snapshot Restore (~1.1s – 1.4s)**: Actors boot instantly from pre-warmed GCS memory snapshots (`SNAPSHOT_FIDELITY_MEMORY`), completely bypassing container pull, OS boot, and runtime initialization.
3. **Zero-Cost State Suspend & Resume**: Put actors to sleep between conversational turns or long agent reasoning tasks. Suspended actors consume **0 vCPU and 0 RAM** while preserving full in-memory state.
4. **Fast Branching & Forking**: Clone a golden snapshot to explore multiple solution branches (e.g. parallel hypothesis testing or code generation trials) simultaneously.

---

## 2. Directory Contents

| File | Description |
|---|---|
| [`adk_minimal_agent.py`](adk_minimal_agent.py) | **Pattern 1: ADK Uses Tools** (~25 lines). Clean, idiomatic ADK Agent using `tools=[sandbox.execute]` and `after_agent_callback` for automatic turn-level sleep/wake. |
| [`microvm_tool.py`](microvm_tool.py) | **Reusable Drop-In ADK Tool & Callback** (`MicroVMSandbox`) providing `execute()`, `run_python()`, and `auto_suspend_callback`. |
| [`adk_code_executor_example.py`](adk_code_executor_example.py) | **Pattern 2: ADK Uses `CodeExecutor`**. Custom `SubstrateMicroVMCodeExecutor(BaseCodeExecutor)` that intercepts ```` ```python ```` code blocks and executes them in a stateful MicroVM with turn-level memory snapshotting. |
| [`adk_actor_template/`](adk_actor_template/) | **Pattern 3: The ADK Agent *Is* the `ActorTemplate`**. Full implementation (`agent.py`, `server.py`, `Dockerfile`, `actortemplate-adk-agent.yaml`, `client_demo.py`) where the entire ADK runtime lives inside the MicroVM memory snapshot. |
| [`adk_agent_sandbox_example.py`](adk_agent_sandbox_example.py) | Diagnostic multi-tool ADK agent demonstrating explicit tool choices (`get_status`, `query`, `suspend`). |
| [`quickstart.sh`](quickstart.sh) | Executable bash demo showing full CLI lifecycle (create, resume, proxy, curl, suspend, delete). |
| [`agent_sandbox_client.py`](agent_sandbox_client.py) | Python SDK context manager for managing actor lifecycles in your Python agent code (automatically loads root `.env`). |
| [`agent_tool_example.py`](agent_tool_example.py) | Multi-turn conversational session manager simulating agent tool calls and turn suspension. |
| [`actortemplate-python-sandbox.yaml`](actortemplate-python-sandbox.yaml) | Manifest template for a stateful Python execution sandbox (`GET /` and `POST /execute`). |

---

## 3. Quickstart: Try It Now

### Option A: Run the CLI Bash Demo
Run the automated end-to-end demo to see an actor spawn, serve requests, and suspend:
```bash
./examples/quickstart.sh
```

**Expected Output:**
```
[Step 1/5] Checking ActorTemplate status... (microvm-actor-template)
[Step 2/5] Creating Actor instance from golden snapshot...
[Step 3/5] Resuming Actor into MicroVM sandbox...
✓ Actor resumed and running in 1479 ms!
[Step 4/5] Establishing secure proxy tunnel and querying sandbox...
Response from Actor Sandbox:
Hello, world!
Version: 1.0.0
Hostname: actor
[Step 5/5] Suspending Actor to release CPU & RAM back to cluster...
✓ Actor suspended and state saved in 1323 ms!
✓ Cleanup complete.
```

---

### Option B: Run the Python Client Benchmark
Test the Python programmatic client:
```bash
python3 examples/agent_sandbox_client.py
```

---

### Option C: Run the Multi-Turn Conversational Tool Simulation
Simulate a multi-turn user conversation where the agent pauses the sandbox between turns to save compute:
```bash
python3 examples/agent_tool_example.py
```

---

### Option D: Pattern 1 — Run the Clean Idiomatic ADK Agent (`tools=[...]`)
Run the clean, production-grade ADK implementation (~25 lines of agent code) with automatic turn-level sleep/wake:
```bash
# Activate your Python virtual environment with google-adk installed (or use ADK_PYTHON_VENV from .env):
source ./ate-dev-env.sh
[[ -n "${ADK_PYTHON_VENV:-}" ]] && source "${ADK_PYTHON_VENV}/bin/activate"
python3 examples/adk_minimal_agent.py
```

---

### Option E: Pattern 1 — Run the Diagnostic Multi-Tool ADK Agent
Run the verbose diagnostic demo where the LLM explicitly chooses separate tools (`get_status`, `query`, `suspend`):
```bash
python3 examples/adk_agent_sandbox_example.py
```

**What this demonstrates in real time:**
1. **Turn 1:** User asks to check and query the sandbox. The ADK Agent calls `get_sandbox_status`, sees no actor exists, then calls `query_microvm_sandbox("/")`. The actor boots into a hardware-isolated MicroVM in **1461ms** and returns HTTP 200.
2. **Turn 2:** User asks to step away and save compute. The ADK Agent calls `suspend_microvm_sandbox()`. The actor freezes its memory state to GCS in **1895ms** and vacates the node (0% CPU/RAM).
3. **Turn 3:** User returns. The ADK Agent restores the actor from snapshot in **1523ms**, queries it, verifies health, and reports back.
4. **Cleanup:** Temporary actors are automatically deleted.

---

### Option F: Pattern 2 — Run the ADK `CodeExecutor` Agent (`code_executor=...`)
Run the ADK agent backed by `SubstrateMicroVMCodeExecutor(BaseCodeExecutor)` and the stateful `python-sandbox-template` MicroVM:
```bash
python3 examples/adk_code_executor_example.py
```
- **Turn 1:** Model emits a ```` ```python ```` block to define a `portfolio` dictionary in MicroVM RAM, then auto-suspends the MicroVM to GCS (`0 CPU / 0 RAM`).
- **Turn 2:** MicroVM wakes from its memory snapshot in **~1.6s** with the `portfolio` variable still in RAM and mutates it in-place.

---

### Option G: Pattern 3 — The ADK Agent *Is* the `ActorTemplate` (Ongoing Stateful Sessions)
In [`examples/adk_actor_template/`](adk_actor_template/), the entire ADK FastAPI runtime (`get_fast_api_app()`) runs *inside* the MicroVM (`adk-agent-actor-template`, built with Cloud Build).

```bash
# 1. Run the initial 2-turn demo (leaves 'adk-user-alice' SUSPENDED in GCS on exit)
python3 examples/adk_actor_template/client_demo.py

# 2. Resume Alice's ongoing stateful conversation in a new process anytime!
python3 examples/adk_actor_template/client_demo.py "What did we write into notes.txt earlier, and what was the kernel version from our very first turn?"

# 3. Optional: Delete Alice's actor when finished
python3 examples/adk_actor_template/client_demo.py --delete
```
See [`examples/adk_actor_template/README.md`](adk_actor_template/README.md) for full details on the Cloud Build setup, `EgressPolicy`, and local metadata credential bridge.

---

### Option H: Interactive Antigravity (`agy`) Session — Port-Forward `ate-api` & Run Code Snippets
This workspace includes an MCP server ([`tools/ate_mcp_server.py`](../tools/ate_mcp_server.py)) that re-uses your existing `ActorTemplate`s (`python-sandbox-template` or `adk-agent-actor-template`) directly with `kubectl`, `kubectl ate`, and HTTP proxy tunnels.

In any `agy` session, you can tell the agent in natural language:
- *"Port-forward our ate-api"*
- *"Run this Python snippet in our sandbox: ..."*
- *"Suspend our sandbox to GCS"*

Under the hood, you can also run the native commands directly against your existing `python-sandbox-template` ([`actortemplate-python-sandbox.yaml`](actortemplate-python-sandbox.yaml)):
```bash
# 1. Port-forward svc/api (127.0.0.1:18443)
kubectl port-forward -n ate-system svc/api 18443:443 &

# 2. Create/resume an actor from the existing python-sandbox-template & proxy port 18880 -> 8080
kubectl ate --endpoint 127.0.0.1:18443 create actor agy-sandbox -a default --template python-sandbox-template
kubectl ate --endpoint 127.0.0.1:18443 resume actor agy-sandbox -a default
kubectl ate --endpoint 127.0.0.1:18443 proxy actor agy-sandbox 18880:8080 -a default &

# 3. Send stateful Python snippets directly to the MicroVM
curl -s http://127.0.0.1:18880/execute -H "Content-Type: application/json" \
  -d '{"code": "portfolio = {\"GOOG\": 150, \"NVDA\": 200}; print(sum(portfolio.values()))"}'

# 4. Check active in-memory variables
curl -s http://127.0.0.1:18880/

# 5. Suspend/resume via port-forwarded ate-api
kubectl ate --endpoint 127.0.0.1:18443 suspend actor agy-sandbox -a default
```

---

## 4. How to Integrate into Agent Frameworks

### 1. Python Context Manager
```python
from agent_sandbox_client import ActorSandbox

# Spawns in ~1.2s, executes, and cleans up automatically
with ActorSandbox(template="microvm-actor-template") as sandbox:
    result = sandbox.get("/")
    print(result["text"])
```

### 2. Google ADK Integration Patterns

#### Pattern 1: ADK Uses Tools (`tools=[...]`)
See [`adk_minimal_agent.py`](adk_minimal_agent.py) and [`microvm_tool.py`](microvm_tool.py):
```python
from google.adk.agents import Agent
from microvm_tool import MicroVMSandbox

# Encapsulates GKE MicroVM lifecycle, session mapping, and proxying
sandbox = MicroVMSandbox(template="microvm-actor-template")

agent = Agent(
    name="coding_agent",
    model="gemini-3.8-flash",
    instruction="Execute tasks in the hardware-isolated microvm sandbox.",
    tools=[sandbox.execute, sandbox.run_python],
    after_agent_callback=sandbox.auto_suspend_callback,  # Auto-freezes compute when idle!
)
```

#### Pattern 2: ADK Uses `CodeExecutor` (`code_executor=...`)
See [`adk_code_executor_example.py`](adk_code_executor_example.py):
```python
from google.adk.agents import Agent
from adk_code_executor_example import SubstrateMicroVMCodeExecutor

microvm_executor = SubstrateMicroVMCodeExecutor(template="python-sandbox-template")

agent = Agent(
    name="microvm_code_executor_agent",
    model="gemini-3.8-flash",
    instruction="Write Python code inside ```python blocks to analyze data.",
    code_executor=microvm_executor,
    after_agent_callback=microvm_executor.auto_suspend_callback,
)
```

#### Pattern 3: The ADK Agent *Is* the `ActorTemplate`
See [`adk_actor_template/`](adk_actor_template/):
- [`adk_actor_template/app/agent.py`](adk_actor_template/app/agent.py): Resident ADK `root_agent` using local bash/file tools and `UnsafeLocalCodeExecutor` safely inside the MicroVM.
- [`adk_actor_template/server.py`](adk_actor_template/server.py): Exposes `get_fast_api_app()`, `/healthz` wakeup probe, and `/auth/token` metadata bridge inside the Actor container.
- [`adk_actor_template/actortemplate-adk-agent.yaml`](adk_actor_template/actortemplate-adk-agent.yaml): `ActorTemplate` (`adk-agent-actor-template`) pinned to the Cloud Build image digest with `SNAPSHOT_FIDELITY_MEMORY`.
- [`adk_actor_template/egress-policy.yaml`](adk_actor_template/egress-policy.yaml): `EgressPolicy` allowing outbound TLS passthrough to `*.googleapis.com:443`.
- [`adk_actor_template/client_demo.py`](adk_actor_template/client_demo.py): Spawns a per-user ADK Agent Actor (`adk-user-alice`), configures egress/auth, sends `/run` requests, and suspends the entire ADK runtime between turns:
  ```bash
  python3 examples/adk_actor_template/client_demo.py
  ```

### 3. LangChain Tool
```python
from langchain.tools import tool
from agent_sandbox_client import ActorSandbox

@tool
def python_repl_sandbox(code: str) -> str:
    """A safe, isolated MicroVM Python REPL environment."""
    with ActorSandbox(template="microvm-actor-template") as sandbox:
        res = sandbox.post("/eval", json_data=code.encode("utf-8"))
        return res["text"]
```

---

## 5. Creating New Actor Templates

To create a new golden snapshot template with pre-installed packages:
```bash
# 1. Apply your template manifest
kubectl ate create actor-template -f examples/actortemplate-python-sandbox.yaml -a default

# 2. View generated golden snapshot tag
kubectl ate get actor-templates -a default

# 3. Spawn actors instantly from that template
kubectl ate create actor my-agent-worker -a default --template python-sandbox-template
kubectl ate resume actor my-agent-worker -a default
```

---

## 6. Monitoring `WorkerPool` Time-Sharing & Capacity

Agent Substrate multiplexes many stateful actors over a fixed `WorkerPool` (`gvisor-pool` and `microvm-pool`):

```bash
# 1. Watch live worker slot, CPU (millicores), and RAM reservations as actors wake and sleep
watch -n 0.5 "kubectl ate get workers; echo ''; kubectl ate top worker; echo ''; kubectl ate get actors -a default"

# 2. Inspect detailed worker capacity, hypervisor overhead (4MiB + 8MiB/GiB), and state transition count
kubectl ate get workers -o yaml

# 3. Inspect which WorkerPool pod a running actor is borrowing (status.workerAssignment)
#    or where a suspended actor's warm snapshot cache resides (status.snapshots[].locality)
kubectl ate get actor adk-user-alice -a default -o yaml

# 4. Compare actual Linux kernel CPU/RSS usage against reserved worker capacity
kubectl top pods -n default -l ate.dev/worker-pool=microvm-pool
```

---

## 7. Developer CLI Reference

```bash
# List all active workers and their capacity
kubectl ate get workers

# Live resource (CPU/Memory) usage and assignment status of workers
kubectl ate top worker

# List registered templates and golden snapshot tags
kubectl ate get actor-templates -A

# List all running or suspended actors
kubectl ate get actors -A

# Forward local port to a running actor
kubectl ate proxy actor <actor-name> 8080:8080 -a default

# Suspend an actor (freeze state to GCS, release node CPU/RAM)
kubectl ate suspend actor <actor-name> -a default

# Resume a suspended actor (instant unfreeze)
kubectl ate resume actor <actor-name> -a default

# Revert actor back to pristine golden snapshot
kubectl ate revert actor <actor-name> -a default
```
