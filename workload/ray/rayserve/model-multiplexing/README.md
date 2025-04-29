# Ray Serve with GCS Fuse as the storage for the model weights

References:

- https://cloud.google.com/kubernetes-engine/docs/how-to/serve-llm-l4-ray#model-multiplexing
- https://github.com/GoogleCloudPlatform/kubernetes-engine-samples/tree/main/ai-ml/gke-ray/rayserve/llm/model-multiplexing

## Getting started

Install the KubeRay operator or enable the GKE Ray add-on

- https://github.com/ray-project/kuberay/blob/master/helm-chart/kuberay-operator/README.md
- https://docs.ray.io/en/latest/serve/production-guide/kubernetes.html

```shell
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm install kuberay-operator kuberay/kuberay-operator --version 1.1.0
```

### Optional, if you want to preload the models from a GCS bucket

The model weights need to be pre-loaded into a GCS bucket, you can use this example script to load the model weights into your bucket

- https://github.com/GoogleCloudPlatform/accelerated-platforms/tree/int-inference-ref-arch/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download

Add permissions for the kubernetes service account `ray-serve` access to the bucket

```shell
PROJECT_ID=your_project_id
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format 'get(projectNumber)')
BUCKET=your_bucket
NAMESPACE=default
KSA=ray-serve

gcloud storage buckets add-iam-policy-binding gs://${BUCKET} \
    --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}$.svc.id.goog/subject/ns/${NAMESPACE}/sa/${KSA}$" \
    --role "roles/storage.objectUser"
```

## Deploy the workload

Adjust variables/settings as needed: GCS Bucket, KSA, etc

```shell
kubectl apply -f ray-service.yaml
```

> NOTE: If downloading from HF, remove GCS references
> NOTE: The `fetch-safetensors` container is [second](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/config.html#containers) on the `workerGroupSpecs` because Ray will automatically inject `ray start` as an argument to the command which will cause the startup to fail. This can be [overwritten](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/pod-command.html) at a cluster level.

## Inference Gateway

- https://cloud.google.com/kubernetes-engine/docs/how-to/deploy-gke-inference-gateway

- Install CRD

```shell
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api-inference-extension/releases/download/v0.3.0/manifests.yaml
```

- Authorization for Metrics scraping

```shell
kubectl apply -f - <<EOF
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: inference-gateway-metrics-reader
rules:
- nonResourceURLs:
  - /metrics
  verbs:
  - get
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: inference-gateway-sa-metrics-reader
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: inference-gateway-sa-metrics-reader-role-binding
  namespace: default
subjects:
- kind: ServiceAccount
  name: inference-gateway-sa-metrics-reader
  namespace: default
roleRef:
  kind: ClusterRole
  name: inference-gateway-metrics-reader
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: v1
kind: Secret
metadata:
  name: inference-gateway-sa-metrics-reader-secret
  namespace: default
  annotations:
    kubernetes.io/service-account.name: inference-gateway-sa-metrics-reader
type: kubernetes.io/service-account-token
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: inference-gateway-sa-metrics-reader-secret-read
rules:
- resources:
  - secrets
  apiGroups: [""]
  verbs: ["get", "list", "watch"]
  resourceNames: ["inference-gateway-sa-metrics-reader-secret"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: gmp-system:collector:inference-gateway-sa-metrics-reader-secret-read
  namespace: default
roleRef:
  name: inference-gateway-sa-metrics-reader-secret-read
  kind: ClusterRole
  apiGroup: rbac.authorization.k8s.io
subjects:
- name: collector
  namespace: gmp-system
  kind: ServiceAccount
EOF
```

- Install Inference Pool

```shell
INFERENCE_POOL=ray-vllm-models
helm install ${INFERENCE_POOL}$ \
  --set inferencePool.modelServers.matchLabels.app=rayserve \
  --set provider.name=gke \
  --version v0.3.0 \
  oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool
```

- Patch Healthcheck Policy for Ray, it uses a different path

```shell
kubectl patch healthcheckpolicy \
  ${INFERENCE_POOL}$ \
  --type merge -p \
  '{"spec":{"default":{"config":{"httpHealthCheck":{"requestPath":"/-/healthz"}}}}}'
```

- Deploy Inference Models

```shell
kubectl apply -f inference-model.yaml
```

- Deploy Gateway and HTTPRoute objects for the Inference Gateway

```shell
kubectl apply -f gateway.yaml
kubectl apply -f httproute.yaml

# get the gateway IP
kubectl get gateway/vllm-lb -o jsonpath='{.status.addresses[0].address}')
```

- Test out querying the gateway EndPoint Picker (EPP)

Replace the IP and Port to your respective deployment settings

```shell
curl -i -X POST 10.0.10.210:80/ -H 'serve_multiplexed_model_id: /gcs/google/gemma-7b-it' -H 'Content-Type: application/json' -d '{"model": "/gcs/google/gemma-7b-it","prompt": "What are the top 5 most popular programming languages? Please be brief."}'

curl -i -X POST 10.0.10.210:80/ -H 'serve_multiplexed_model_id: /gcs/meta-llama/Meta-Llama-3-8B-Instruct' -H 'Content-Type: application/json' -d '{"model": "/gcs/meta-llama/Meta-Llama-3-8B-Instruct","prompt": "What are the top 5 most popular programming languages? Please be brief."}'
```

> NOTE: If testing from HF, remove the `/gcs/` prefix.

## Misc

Set your HuggingFace token to pull the data

If you are not pulling from GCS and directly from HF, set your secret

```shell
export HF_TOKEN=
kubectl create secret generic hugging-face-token-secret \
    --from-literal=HUGGING_FACE_TOKEN=${HF_TOKEN} \
    --dry-run=client -o yaml | k apply  -f -
```

```shell
gcloud compute networks subnets create kh-central1-proxyonly \
    --purpose=REGIONAL_MANAGED_PROXY \
    --role=ACTIVE \
    --region=us-central1 \
    --network=kenthua-vpc \
    --range=10.0.100.0/23
```

> NOTE: NotSupportedByGateway: Bind of InferencePool "default/ray-vllm-models" to GatewayRef "default/vllm-lb" failed: Unsupported gateway: gatewayclass gke-l7-global-external-managed does not support inference pools
