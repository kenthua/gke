# Agent Substrate on GKE with ComputeClass

This directory contains the production-ready Kubernetes manifests, ComputeClass definitions, environment configs, and automation scripts for deploying **Agent Substrate (v1.0.0)** on Google Kubernetes Engine (GKE) using GKE **ComputeClass** and Node Auto-Provisioning (NAP).

Reference documentation: [GKE Agent Substrate Overview](https://docs.cloud.google.com/kubernetes-engine/ai-ml/install-overview-substrate)

---

## Architecture: How Agent Substrate Works with ComputeClass

Agent Substrate is an actor-based execution runtime designed to run stateful AI agent sandboxes at high density. Instead of dedicating long-running Pods to mostly-idle agents, Substrate decouples agent state from pods by maintaining pre-warmed worker sandboxes (`WorkerPool`) and snapshotting idle agents to Cloud Storage.

Integrating Agent Substrate with GKE `ComputeClass` (`cloud.google.com/v1`) enables dynamic, automated provisioning of optimized GKE nodes without managing static node pools:

```
+-----------------------------------------------------------------------------------+
| GKE Standard Cluster (${CLUSTER_NAME})                                            |
|                                                                                   |
|  ComputeClass: substrate-n2                                                       |
|  - Machine: n2-standard-4 (pd-balanced boot disk)                                 |
|  - Nested Virtualization: enableNestedVirtualization=true (/dev/kvm)              |
|  - High-Density Sysctls: fs.inotify, fs.aio-max-nr, max_map_count, podPidsLimit   |
|  - Node SA: ${NODE_SA_EMAIL}                                                      |
+-----------------------------------------------------------------------------------+
           |                                                      |
           v GKE NAP creates n2 nodes                              v Schedules non-DaemonSets
+------------------------------------+               +------------------------------+
| WorkerPool: gvisor-pool / microvm   |               | Namespace: ate-system        |
| spec.template.nodeSelector:        |               | Label:                       |
|   cloud.google.com/compute-class:  |               |  cloud.google.com/           |
|     substrate-n2                   |               |  default-compute-class-      |
| (GKE auto-injects tolerations)     |               |  non-daemonset=substrate-n2  |
|                                    |               |                              |
| Sandboxes: gVisor / MicroVM (KVM)  |               | Pods: ateapi, atecontroller, |
|                                    |               | postgres-0 (2 vCPU)          |
+------------------------------------+               +------------------------------+
           |                                                      |
           +--------------------------+---------------------------+
                                      |
                                      v
           +------------------------------------------------------+
           | atelet (DaemonSet on all nodes)                      |
           | Toleration: cloud.google.com/compute-class (Exists)  |
           +------------------------------------------------------+
```

### 1. atelet DaemonSet Tolerations
The upstream `atelet` DaemonSet in Agent Substrate v1.0.0 already includes:
```yaml
tolerations:
- key: cloud.google.com/compute-class
  operator: Exists
  effect: NoSchedule
```
Therefore, `atelet` automatically schedules on any node provisioned by GKE for a ComputeClass.

### 2. Targeting from a WorkerPool
In any `WorkerPool`, set `spec.template.nodeSelector`:
```yaml
template:
  nodeSelector:
    cloud.google.com/compute-class: substrate-n2
```
GKE automatically injects the matching `cloud.google.com/compute-class=substrate-n2:NoSchedule` toleration onto the worker pods, prompting GKE Node Auto-Provisioning (NAP) to provision and autoscale `n2-standard-4` nodes matching the ComputeClass spec.

### 3. Targeting `ate-system` Control Plane Without Manifest Patches
By labeling the `ate-system` namespace:
```bash
kubectl label namespace ate-system \
  cloud.google.com/default-compute-class-non-daemonset=substrate-n2 --overwrite
```
GKE automatically schedules all non-DaemonSet pods in `ate-system` (including `ate-api-server`, `ate-controller`, `atenet-router`, and the 2-vCPU `postgres-0` StatefulSet) onto `substrate-n2` nodes, while DaemonSets (`atelet`, `k8s-credential-provider`) remain free to run across all cluster nodes.

---

## File Catalog

| File | Purpose |
|---|---|
| [`.env.example`](.env.example) | Template for local `.env` configuration (project ID, project number, cluster, service accounts, and Cloud Build image digest). |
| [`substrate-computeclass.yaml`](substrate-computeclass.yaml) | Primary on-demand `n2-standard-4` ComputeClass spec with nested virtualization, high-density kernel sysctls, and PID limits. |
| [`substrate-computeclass-spot.yaml`](substrate-computeclass-spot.yaml) | Spot-first ComputeClass variant for cost-effective dev/test environments with on-demand fallback. |
| [`ate-system-namespace.yaml`](ate-system-namespace.yaml) | `ate-system` namespace manifest pre-configured with the default ComputeClass label. |
| [`workerpool-gvisor.yaml`](workerpool-gvisor.yaml) | Agent Substrate WorkerPool spec for gVisor sandboxes targeting `substrate-n2`. |
| [`workerpool-microvm.yaml`](workerpool-microvm.yaml) | Agent Substrate WorkerPool spec for microVM (hardware-isolated) sandboxes targeting `substrate-n2`. |
| [`actortemplate-example.yaml`](actortemplate-example.yaml) | Sample ActorTemplate defining container image, environment, and memory snapshot fidelity for stateful agents. |
| [`actortemplate-microvm.yaml`](actortemplate-microvm.yaml) | ActorTemplate configured specifically for MicroVM worker pool sandboxes. |
| [`ate-dev-env.sh`](ate-dev-env.sh) | Sourced shell configuration defining project, region, cluster context, GCS bucket names, and SPIFFE IDs (automatically loads `.env` if present). |
| [`setup.sh`](setup.sh) | Automated bash script to validate, apply manifests, provision buckets, and configure the cluster. |
| [`tools/ate_mcp_server.py`](tools/ate_mcp_server.py) | MCP server exposing Agent Substrate MicroVM sandbox execution and lifecycle controls (`execute_code`, `suspend_sandbox`, `resume_sandbox`). |
| [`crds/`](crds/) | Upstream Agent Substrate Custom Resource Definitions (`WorkerPool`, `SandboxConfig`, `CSIDriverConfig`). |
| [`overlay/`](overlay/) | GKE monitoring manifests (`atenet-router-monitoring.yaml`) and Cloud SQL kustomize components. |
| [`examples/`](examples/) | Complete runnable examples, Python SDK client, and AI agent integration guides. |

---

## Quickstart & Execution Steps

### Step 1: Configure `.env` and Source Environment Variables
Copy `.env.example` to `.env` (git-ignored) and set your GCP project and cluster details:
```bash
cp .env.example .env
# Edit .env with your PROJECT_ID, PROJECT_NUMBER, and CLUSTER_NAME, then source:
source ./ate-dev-env.sh
```
*(Note: All Python examples in `examples/` also automatically load `.env` from the repository root.)*

### Step 2: Run Automated Setup
To apply the ComputeClass, namespace, CRDs, GCS buckets, and WorkerPools in one command:
```bash
./setup.sh
```

### Step 3: Manual Step-by-Step (Alternative)

1. **Apply the ComputeClass:**
   ```bash
   source ./ate-dev-env.sh
   envsubst < substrate-computeclass.yaml | kubectl apply -f -
   kubectl get computeclass substrate-n2
   ```

2. **Prepare the `ate-system` Namespace:**
   ```bash
   kubectl apply -f ate-system-namespace.yaml
   ```

3. **Install CRDs:**
   ```bash
   kubectl apply -f crds/
   ```

4. **Deploy the Agent Substrate Control Plane:**
   Deploy using `ate-setup` from the Substrate CLI:
   ```bash
   go run ./cmd/ate-setup deploy ate-system \
     --image-repo=${ATE_IMAGE_REPO} \
     --image-tag=${ATE_IMAGE_TAG} \
     --credential-provider='{"name":"k8s.io"}' \
     --ingress-allowed-spiffe-ids="${ATE_INGRESS_ALLOWED_SPIFFE_IDS}" \
     --snapshot-location="${SNAPSHOT_LOCATION}" \
     --snapshot-transfer-gsa-name="${SNAPSHOT_TRANSFER_GSA_NAME}" \
     --storage-bucket-name="${BUCKET_NAME}" \
     --gcp-project-id="${PROJECT_ID}" \
     --gcp-cluster-name="${CLUSTER_NAME}" \
     --gcp-cluster-location="${CLUSTER_LOCATION}"
   ```

5. **Deploy WorkerPools:**
   ```bash
   kubectl apply -f workerpool-gvisor.yaml
   kubectl apply -f workerpool-microvm.yaml
   ```

6. **Verify Dynamic Node Provisioning:**
   ```bash
   kubectl get pods -n default -o wide
   kubectl get nodes -l cloud.google.com/compute-class=substrate-n2
   ```

7. **Create an Actor Template & Launch an Agent (gVisor or MicroVM):**
   ```bash
   # Launch a gVisor Actor:
   kubectl ate create actor-template -f actortemplate-example.yaml
   kubectl ate create actor my-gvisor-actor -a default --template hello-actor-template

   # Launch a MicroVM (Hardware-isolated Cloud Hypervisor) Actor:
   kubectl ate create actor-template -f actortemplate-microvm.yaml
   kubectl ate create actor my-microvm-actor -a default --template microvm-actor-template
   kubectl ate resume actor my-microvm-actor -a default
   ```

---

## Dedicated MicroVM Node Pool (N2 with Nested Virtualization)

For workloads requiring hardware-assisted nested virtualization (`/dev/kvm`), ensure the following:

1. **Organization Policy Prerequisite:**
   Google Cloud projects must have nested virtualization enabled:
   ```bash
   gcloud resource-manager org-policies disable-enforce compute.disableNestedVirtualization --project=${PROJECT_ID}
   ```

2. **Dedicated N2 Node Pool Provisioning:**
   ```bash
   gcloud container node-pools create substrate-microvm-nodes \
     --cluster=${CLUSTER_NAME} \
     --region=${GCE_REGION} \
     --node-locations=us-central1-b \
     --machine-type=n2-standard-4 \
     --enable-nested-virtualization \
     --service-account="${NODE_SA_EMAIL}" \
     --disk-type=pd-balanced \
     --disk-size=100 \
     --num-nodes=1 \
     --enable-autoscaling --min-nodes=1 --max-nodes=3 \
     --node-labels="cloud.google.com/compute-class=substrate-n2" \
     --node-taints="cloud.google.com/compute-class=substrate-n2:NoSchedule,ate.dev/sandboxClass=microvm:NoSchedule"
   ```

---

## AI Agent Examples & Integration

See the [`examples/`](examples/) directory for runnable scripts and patterns to leverage the deployed MicroVM actors across all three **Google ADK + Agent Substrate** integration architectures:

| Pattern | Where ADK Runs | How Actor Is Invoked | What Is Snapshotted to GCS | Example Files |
|---|---|---|---|---|
| **1. ADK Uses Tools** (`tools=[...]`) | Outside the Actor | Structured `FunctionCall` (`sandbox.execute`, `sandbox.run_python`) | Tool sandbox memory & filesystem | [`adk_minimal_agent.py`](examples/adk_minimal_agent.py), [`microvm_tool.py`](examples/microvm_tool.py), [`adk_agent_sandbox_example.py`](examples/adk_agent_sandbox_example.py) |
| **2. ADK Uses `CodeExecutor`** (`code_executor=...`) | Outside the Actor | Emitting ```` ```python ```` blocks intercepted by `SubstrateMicroVMCodeExecutor(BaseCodeExecutor)` | Persistent Python REPL globals & filesystem | [`adk_code_executor_example.py`](examples/adk_code_executor_example.py), [`actortemplate-python-sandbox.yaml`](examples/actortemplate-python-sandbox.yaml) |
| **3. ADK Agent *Is* the `ActorTemplate`** | **Inside** the MicroVM Actor (`adk-agent-actor-template`) | Direct `/run` HTTP calls to per-user actor (`adk-user-alice`) | **Entire ADK FastAPI runtime**, `InMemorySessionService`, local tools, and `/tmp/workspace` | [`examples/adk_actor_template/`](examples/adk_actor_template/) ([`README.md`](examples/adk_actor_template/README.md), [`client_demo.py`](examples/adk_actor_template/client_demo.py)) |

Additional utilities in [`examples/`](examples/) and [`tools/`](tools/):
- [`tools/ate_mcp_server.py`](tools/ate_mcp_server.py): MCP server for port-forwarding `ate-api` (`127.0.0.1:18443`) and running stateful code snippets directly against existing `ActorTemplate`s (`python-sandbox-template` / `adk-agent-actor-template`).
- [`examples/quickstart.sh`](examples/quickstart.sh): Automated bash demo showing full actor lifecycle (create, resume in ~1.2s, proxy, suspend, delete).
- [`examples/agent_sandbox_client.py`](examples/agent_sandbox_client.py): Python context-manager SDK (`ActorSandbox`) supporting both ephemeral (`auto_delete=True`) and ongoing stateful (`auto_delete=False`) actor sessions.
- [`examples/agent_tool_example.py`](examples/agent_tool_example.py): Multi-turn conversational session manager demonstrating turn-level suspension to save compute.
- [`examples/README.md`](examples/README.md): Detailed architectural and agent framework integration guide (Gemini, Google ADK, LangChain).

---

## Deployed `ActorTemplate` Catalog (`default` atespace)

| Template Name | Image | Purpose |
|---|---|---|
| `hello-actor-template` | `gke/hello-app` | Sample HTTP server running on `gvisor-pool`. |
| `microvm-actor-template` | `gke/hello-app` | Hardware-isolated HTTP sandbox running on `microvm-pool`. |
| `python-sandbox-template` | `python:3.11-slim` | Stateful Python execution server (`GET /`, `POST /execute`) for ADK Tools & `BaseCodeExecutor`. |
| `adk-agent-actor-template` | `apps/adk-actor-agent` (Cloud Build) | Full resident Google ADK Agent (`get_fast_api_app()`) snapshotted in MicroVM memory. |

---

## Monitoring `WorkerPool` Time-Sharing & Capacity

To observe how Agent Substrate multiplexes active and suspended actors across your `WorkerPool` pods in real time:

```bash
# Live worker slot reservations (ACTORS, CPU millicores, MEMORY)
kubectl ate get workers

# Live worker assignment status (FREE vs ASSIGNED) and actual CPU/Memory usage
kubectl ate top worker

# Watch workers and actors side-by-side during multi-turn ADK execution
watch -n 0.5 "kubectl ate get workers; echo ''; kubectl ate top worker; echo ''; kubectl ate get actors -a default"

# Inspect which worker pod a running actor is assigned to (status.workerAssignment)
# or which node holds a suspended actor's warm snapshot cache (status.snapshots[].locality)
kubectl ate get actor adk-user-alice -a default -o yaml
```
