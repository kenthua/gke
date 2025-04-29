# Inference Gateway + Ray Serve with GCS Fuse as the storage for the model weights

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

- Adjust variables/settings as needed: GCS Bucket, KSA, etc

```shell
kubectl apply -f ray-service.yaml
```

> NOTE: If downloading from HF, remove GCS references
> NOTE: The `fetch-safetensors` container is [second](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/config.html#containers) on the `workerGroupSpecs` because Ray will automatically inject `ray start` as an argument to the command which will cause the startup to fail. This can be [overwritten](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/pod-command.html) at a cluster level.

- Check the service deployment status

```shell
kubectl describe rayservice model-multiplexing
```

Example output

```shell
Status:
  Active Service Status:
    Application Statuses:
      Llm:
        Health Last Update Time:  2025-04-30T02:28:07Z
        Serve Deployment Statuses:
          Multi Model Deployment:
            Health Last Update Time:  2025-04-30T02:28:07Z
            Status:                   HEALTHY
          VLLM Deployment:
            Health Last Update Time:  2025-04-30T02:28:07Z
            Status:                   HEALTHY
          VLLMDeployment_1:
            Health Last Update Time:  2025-04-30T02:28:07Z
            Status:                   HEALTHY
        Status:                       RUNNING
    Ray Cluster Name:                 model-multiplexing-raycluster-l4lwg
    Ray Cluster Status:
      Available Worker Replicas:  2
      Desired CPU:                42
      Desired GPU:                5
      Desired Memory:             88Gi
      Desired TPU:                0
      Desired Worker Replicas:    2
      Endpoints:
        Client:        10001
        Dashboard:     8265
        Gcs - Server:  6379
        Metrics:       8080
        Serve:         8000
      Head:
        Pod IP:             10.3.128.200
        Service IP:         34.118.234.245
      Last Update Time:     2025-04-30T02:26:13Z
      Max Worker Replicas:  4
      Observed Generation:  1
      State:                ready
```

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
kubectl get gateway/vllm-lb -o jsonpath='{.status.addresses[0].address}'
```

- Test out querying the gateway EndPoint Picker (EPP)

Replace the IP and Port to your respective deployment settings.

> NOTE: Ray Service uses the [HTTP header](https://docs.ray.io/en/latest/serve/model-multiplexing.html#writing-a-multiplexed-deployment) `serve_multiplexed_model_id` to designate the model to be served. This is propagated from the EPP to the ray serve endpoint.

```shell
IP=$(kubectl get gateway/vllm-lb -o jsonpath='{.status.addresses[0].value}')

curl -i -X POST http://$IP:80/ -H 'serve_multiplexed_model_id: /gcs/google/gemma-2-9b-it' -H 'Content-Type: application/json' -d '{"model": "/gcs/google/gemma-2-9b-it","prompt": "What are the top 5 most popular programming languages? Please be brief."}'

curl -i -X POST http://$IP:80/ -H 'serve_multiplexed_model_id: /gcs/meta-llama/Llama-3.1-8B-Instruct' -H 'Content-Type: application/json' -d '{"model": "/gcs/meta-llama/Llama-3.1-8B-Instruct","prompt": "What are the top 5 most popular programming languages? Please be brief."}'
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
