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

The model weights need to be pre-loaded into a GCS bucket, you can use this example script to load the model weights into your bucket

- https://github.com/GoogleCloudPlatform/accelerated-platforms/tree/int-inference-ref-arch/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download

Add permissions for the kubernetes service account `ray-serve` access to the bucket

```shell
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

> NOTE: The `fetch-safetensors` container is [second](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/config.html#containers) on the `workerGroupSpecs` because Ray will automatically inject `ray start` as an argument to the command which will cause the startup to fail. This can be [overwritten](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/pod-command.html) at a cluster level.

## Misc

Set your HuggingFace token to pull the data

If you are not pulling from GCS and directly from HF, set your secret

```shell
export HF_TOKEN=
kubectl create secret generic hugging-face-token-secret \
    --from-literal=HUGGING_FACE_TOKEN=${HF_TOKEN} \
    --dry-run=client -o yaml | k apply  -f -
```
