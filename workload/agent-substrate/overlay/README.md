# GKE kustomize content

agent-substrate/substrate is moving the GKE-specific parts of its control
plane manifests (`manifests/ate-install`) out of its tree. They live here now.

| Path | What it is |
| :--- | :--- |
| `components/gke/` | A kustomize Component with GKE's patches. It appends the `cloud.google.com/compute-class` toleration to atelet's DaemonSet, so atelet runs on the nodes GKE creates for a ComputeClass, and points `ate-otel-config`'s `OTEL_EXPORTER_OTLP_ENDPOINT` at GKE's managed OpenTelemetry collector. Each patch targets its object by name, so a stream without that object is left alone. |
| `resources/atenet-router-monitoring.yaml` | The PodMonitoring that has Google Managed Prometheus scrape the Envoy router. The "Substrate Routing & E2E Latency" dashboard reads it. It is a plain resource, not part of the Component, because `ate-setup deploy --component` rejects components that add resources. |
| `components/cloudsql/` | A Component that adds the Cloud SQL Auth Proxy sidecar to ate-api-server, for the PostgreSQL store on Cloud SQL ([cloud-sql.md](../../tools/setup-gcp/cloud-sql.md)). Upstream's ate-setup applied it itself and wrote the proxy's settings; with this component the install has to supply those settings. Its `kustomization.yaml` lists them. The installer does not use it. |

The agentgateway router's OTLP address (`AGENTGATEWAY_OTLP_ADDRESS` in
upstream's `components/agentgateway`) is not here: the installer deploys only
the Envoy router.

## How the installer applies it today

Upstream's ate-setup cannot take extra components yet: `ate-setup deploy
--component` (agent-substrate/substrate PR 3179) and `ate-setup render`
(agent-substrate/substrate#3240) are not merged. Until one is, the installer
adds this content to the Substrate tree it fetched, right before it runs
`ate-setup deploy ate-system` there (the deploy step's first checklist row):

1. It checks for upstream's `manifests/ate-install/atenet-router-monitoring.yaml`.
   A tree that still has it (every release up to v0.6.0, and main until the
   move merges) also still has the toleration and the endpoint, so nothing is
   added; adding it there would duplicate them.
2. Otherwise it copies `components/gke` to
   `manifests/ate-install/components/substrate-gke` and `resources/` to
   `manifests/ate-install/substrate-gke/`, and lists them in
   `manifests/ate-install/base/kustomization.yaml`, under `components:` and
   `resources:`. That is the kustomization ate-setup renders for a GKE install
   with the Envoy router. Running it again changes nothing.
3. It keeps the change out of `git status` in that tree (`.git/info/exclude`
   and `git update-index --skip-worktree`), so images built from it are not
   stamped `-dirty`.

The upgrade step does the same to the installed and the new trees it fetches
for upstream's runbook, and so does `go run . --fetch-substrate`. A checkout
you pass with `--substrate-root` is never modified: the deploy step only warns
if it needs this content. To add it to such a checkout yourself, run this
from `installer/`:

```bash
go run . --add-gke-overlay /path/to/substrate
```

The code is in [`installer/internal/gkeoverlay`](../../installer/internal/gkeoverlay).

### Known limitation

Only `ate-setup deploy ate-system` renders `base/`. Upstream's single-component
deploys (`ate-setup deploy atelet`, `deploy apiserver` and so on) apply the raw
manifests and do not carry these patches. The installer runs only the full
`deploy ate-system`.

## Later: `ate-setup deploy --component`

Once a Substrate release the installer pins has `ate-setup deploy
--component`, the installer passes `--component deploy/gke/components/gke` to
`ate-setup deploy ate-system`, applies `resources/` itself, and stops editing
the tree. `components/gke` is a Component with patches only, so it can be
passed as it is. `components/cloudsql` can be passed the same way by an
install that uses Cloud SQL.
