# Inference Gateway + Ray Serve with GCS Fuse as the storage for the model weights

References:

- https://cloud.google.com/kubernetes-engine/docs/how-to/serve-llm-l4-ray#model-multiplexing
- https://github.com/GoogleCloudPlatform/kubernetes-engine-samples/tree/main/ai-ml/gke-ray/rayserve/llm/model-multiplexing

## Getting started

- Deploy a GKE Autopilot cluster

```shell
CLUSTER_NAME=mycluster
PROJECT_ID=yourproject
REGION=us-central1

gcloud beta container clusters create-auto $CLUSTER_NAME \
  --project $PROJECT_ID \
  --region $REGION \
  --release-channel "rapid" \
  --enable-dns-access \
  --enable-ray-operator \
  --enable-ray-cluster-logging \
  --enable-ray-cluster-monitoring \
  --auto-monitoring-scope=ALL
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

This is using the newer [LLMConfig/LLMRouter](https://docs.ray.io/en/releases-2.45.0/serve/llm/serving-llms.html) implementation

```shell
kubectl apply -f ray-service-llm.yaml
```

> NOTE: If downloading from HF, use `kubectl apply -f ray-service-llm-hf.yaml`
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
      llm_app:
        Health Last Update Time:  2025-05-01T01:13:54Z
        Serve Deployment Statuses:
          LLMDeployment:--gcs--google--gemma-2-9b-it:
            Health Last Update Time:  2025-05-01T01:13:54Z
            Status:                   HEALTHY
          LLMDeployment:--gcs--meta-llama--Llama-3_1-8B-Instruct:
            Health Last Update Time:  2025-05-01T01:13:54Z
            Status:                   HEALTHY
          LLM Router:
            Health Last Update Time:  2025-05-01T01:13:54Z
            Status:                   HEALTHY
        Status:                       RUNNING
    Ray Cluster Name:                 model-multiplexing-raycluster-f7tpw
    Ray Cluster Status:
      Available Worker Replicas:  2
      Desired CPU:                42
      Desired GPU:                4
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
        Pod IP:             10.252.0.35
        Service IP:         34.118.230.122
      Last Update Time:     2025-05-01T01:07:08Z
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

```shell
IP=$(kubectl get gateway/vllm-lb -o jsonpath='{.status.addresses[0].value}')

curl -i -X POST $IP:80/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "/gcs/google/gemma-2-9b-it","prompt": "What are the top 5 most popular programming languages? Please be brief."}'

curl -i -X POST $IP:80/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "/gcs/meta-llama/Llama-3.1-8B-Instruct","prompt": "What are the top 5 most popular programming languages? Please be brief."}'
```

> NOTE: If testing from HF, remove the `/gcs/` prefix.

Output

```json
{
  "choices": [
    {
      "finish_reason": "stop",
      "index": 0,
      "logprobs": {
        "text_offset": [],
        "token_logprobs": [],
        "tokens": [],
        "top_logprobs": []
      },
      "prompt_logprobs": null,
      "stop_reason": null,
      "text": "\n\n1. **Python** \n2. **JavaScript**\n3. **Java**\n4. **C#**\n5. **C++**\n\nNote: Popularity rankings can change slightly based on the specific index used. \n"
    }
  ],
  "created": 1746062176,
  "id": "/gcs/google/gemma-2-9b-it-26c4289c-977e-4a4a-bf7e-5ec45600d2a9",
  "model": "/gcs/google/gemma-2-9b-it",
  "object": "text_completion",
  "usage": {
    "completion_tokens": 52,
    "prompt_tokens": 16,
    "prompt_tokens_details": null,
    "total_tokens": 68
  }
}

{
  "choices": [
    {
      "finish_reason": "stop",
      "index": 0,
      "logprobs": {
        "text_offset": [],
        "token_logprobs": [],
        "tokens": [],
        "top_logprobs": []
      },
      "prompt_logprobs": null,
      "stop_reason": null,
      "text": " Written by a normal English language user with no expertise in the use of programming languages.\nThe top 5 most popular programming languages are:\n1. Python - easy to learn and often used in data analysis, machine learning, artificial intelligence, and creating web applications.\n2. Java - widely used for web development, Android apps, and games, especially with its large community and varied libraries.\n3. JavaScript - commonly used for building interactive client-side web applications and creating visual effects and dynamic behavior on websites.\n4. C++ - powerful and highly versatile, often used for developing operating systems, games, and high-performance applications.\n5. SQL - responsible for database management and creation, including storing, modifying, and retrieving data.\n\nPlease note: Rankings may vary depending on the source and the specific use case.\n\nWould you like me to elaborate on any of these programming languages?"
    }
  ],
  "created": 1746062332,
  "id": "/gcs/meta-llama/Llama-3.1-8B-Instruct-48ee36cd-925b-4e10-88b6-4f7e78781c87",
  "model": "/gcs/meta-llama/Llama-3.1-8B-Instruct",
  "object": "text_completion",
  "usage": {
    "completion_tokens": 174,
    "prompt_tokens": 16,
    "prompt_tokens_details": null,
    "total_tokens": 190
  }
}
```

## Misc

- KubeRay Operator Options

  Install the KubeRay operator or enable the GKE Ray add-on (references)

  - https://github.com/ray-project/kuberay/blob/master/helm-chart/kuberay-operator/README.md
  - https://docs.ray.io/en/latest/serve/production-guide/kubernetes.html

  - Update your existing cluster with the [RayOperator enabled](https://cloud.google.com/kubernetes-engine/docs/add-on/ray-on-gke/how-to/enable-ray-on-gke#gcloud)

  ```shell
  #example
  gcloud container clusters update $CLUSTER_NAME \
    --location $REGION/ZONE \
    --update-addons=RayOperator=ENABLED
  ```

  - Alternative, manually install the KubeRay operator into your cluster

  ```shell
  helm repo add kuberay https://ray-project.github.io/kuberay-helm/
  helm install kuberay-operator kuberay/kuberay-operator --version 1.3.2
  ```

- Set your HuggingFace token to pull the data

If you are not pulling from GCS and directly from HF, set your secret

```shell
export HF_TOKEN=
kubectl create secret generic hugging-face-token-secret \
    --from-literal=HUGGING_FACE_TOKEN=${HF_TOKEN} \
    --dry-run=client -o yaml | k apply  -f -
```

- Setting up a proxyonly subnet for regional internal/external LBs for the gateway

```shell
gcloud compute networks subnets create kh-central1-proxyonly \
    --purpose=REGIONAL_MANAGED_PROXY \
    --role=ACTIVE \
    --region=us-central1 \
    --network=kenthua-vpc \
    --range=10.0.100.0/23
```

- Ray Serve Autoscaler, which will also trigger the Ray in-tree autoscaler for workergroups

Scaling Up

```shell
INFO 2025-05-02 16:03:20,094 controller 521 -- Replica(id='ehddpq4d', deployment='LLMRouter', app='llm_app') started successfully on node 'd0c51419f7606128f6ace540631062143c6495a304a1e16625857a46' after 282.8s (PID: 1751). Replica constructor, reconfigure method, and initial health check took 0.1s.
INFO 2025-05-02 16:42:12,905 controller 521 -- Upscaling Deployment(name='LLMDeployment:--gcs--meta-llama--Llama-3_2-1B-Instruct', app='llm_app') from 1 to 4 replicas. Current ongoing requests: 4.88, current running replicas: 1.
INFO 2025-05-02 16:42:12,907 controller 521 -- Adding 3 replicas to Deployment(name='LLMDeployment:--gcs--meta-llama--Llama-3_2-1B-Instruct', app='llm_app').
INFO 2025-05-02 16:42:12,907 controller 521 -- Starting Replica(id='85pivh7x', deployment='LLMDeployment:--gcs--meta-llama--Llama-3_2-1B-Instruct', app='llm_app').
```

Scaling Down

```shell
INFO 2025-05-02 16:51:20,294 controller 521 -- Replica(id='dkjrdp2p', deployment='LLMDeployment:--gcs--meta-llama--Llama-3_2-1B-Instruct', app='llm_app') started successfully on node '44c91631257e4c819fb9991e5898a19ffb01d6e05adb2773b60a40d6' after 547.4s (PID: 824). Replica constructor, reconfigure method, and initial health check took 95.3s.
INFO 2025-05-02 17:03:32,417 controller 521 -- Downscaling Deployment(name='LLMDeployment:--gcs--meta-llama--Llama-3_2-1B-Instruct', app='llm_app') from 4 to 1 replicas. Current ongoing requests: 0.93, current running replicas: 4.
INFO 2025-05-02 17:03:32,419 controller 521 -- Removing 3 replicas from Deployment(name='LLMDeployment:--gcs--meta-llama--Llama-3_2-1B-Instruct', app='llm_app').
INFO 2025-05-02 17:03:32,421 controller 521 -- Stopping Replica(id='a7myhweb', deployment='LLMDeployment:--gcs--meta-llama--Llama-3_2-1B-Instruct', app='llm_app') (currently ReplicaState.RUNNING).
```

- Autoscaling

In-tree Ray Worker, when using the `spec.serveConfigV2.applications[0].args.llm_configs[0].accelerator_type=L4`,
it references the requirement of `0.001` and the worker/node provides the resource `accelerator_type:L4: 1.0`, worker autoscale is not triggered.

As a result, `accelerator_type` while it, scales the workload replicas, up to the available workers. New workers are not triggered.

```shell
Table:
------------------------------
    NODE_ID                                                   NODE_IP      IS_HEAD_NODE    STATE    STATE_MESSAGE    NODE_NAME    RESOURCES_TOTAL                  LABELS
 0  1bef713dbcd1eddf12a7c0923afd7f02ba1c7a65bf478dd0fe4682e5  10.252.7.11  False           ALIVE                     10.252.7.11  CPU: 20.0                        ray.io/node_id: 1bef713dbcd1eddf12a7c0923afd7f02ba1c7a65bf478dd0fe4682e5
                                                                                                                                  GPU: 2.0
                                                                                                                                  accelerator_type:L4: 1.0
                                                                                                                                  memory: 40.000 GiB
                                                                                                                                  node:10.252.7.11: 1.0
                                                                                                                                  object_store_memory: 11.959 GiB
```

Is this the actual reason in that it think it doesn't need to, but GPU from `tensor_parallel_size` should trigger it.

```shell
1.734723475976807e-18/1.0 accelerator_type:L4 (0.0 used of 0.002 reserved in placement groups)
```
