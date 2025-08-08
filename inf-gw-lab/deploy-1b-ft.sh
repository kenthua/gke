#!/bin/bash

DEPLOY_TYPE=$(echo "$1" | tr '[:upper:]' '[:lower:]')

if [ "$DEPLOY_TYPE" != "tpu" ] && [ "$DEPLOY_TYPE" != "gpu" ]; then
  DEPLOY_TYPE="gpu"
fi

echo "### Set env"
export PROJECT_ID=$(gcloud config get-value project)
export CLUSTER_NAME=vllm-inference
export REGION=$(gcloud compute project-info describe \
--format="value(commonInstanceMetadata.items[google-compute-default-region])")
export FT_LORA_ADAPTER_PATH=
export BUCKET=$PROJECT_ID

echo "### Get cluster"
gcloud container clusters get-credentials $CLUSTER_NAME \
--region $REGION \
--project $PROJECT_ID

echo "### Create HF secret"
kubectl create secret generic hf-secret \
      --from-literal=hf_api_token=$HF_TOKEN \
      --dry-run=client -o yaml | kubectl apply -f -

echo "### Deploy gemma 3 1b fine-tuned"
if [ "$DEPLOY_TYPE" = "gpu" ]; then
  envsubst < gemma-3-1b-ft-lora.yaml.tmpl > gemma-3-1b-ft-lora.yaml
  kubectl apply -f gemma-3-1b-ft-lora.yaml
else
  envsubst < tpu-gemma-3-1b-ft.yaml.tmpl > tpu-gemma-3-1b-ft.yaml
  kubectl apply -f tpu-gemma-3-1b-ft.yaml
fi

echo "### Deploy Gradio"
kubectl apply -f gradio.yaml

echo "### Deploy gateway"
kubectl apply -f gateway.yaml

echo "### Deploy HTTPRoute for gemma 3 1b"
kubectl apply -f hr-gemma-3-1b.yaml

echo "### Deploy HTTPRoute for gemma 3 1b ft"
kubectl apply -f hr-gemma-3-1b-ft.yaml

echo "### Deploy body-based routing"
helm install bbr \
  --version v0.5.1 \
  --set provider.name=gke \
  --set inferenceGateway.name=vllm-xlb \
oci://registry.k8s.io/gateway-api-inference-extension/charts/body-based-routing

echo "### Deploy Inference Pool for gemma 3 1b"
INFERENCE_POOL=vllm-gemma-3-1b
helm install ${INFERENCE_POOL} \
  --set inferencePool.modelServers.matchLabels.app=vllm-gemma-3-1b \
  --set provider.name=gke \
  --version v0.5.1 \
  --set inferenceExtension.replicas=2 \
  oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool \
  -f epp-values.yaml

echo "### Deploy Inference Model for gemma 3 1b"
kubectl apply -f im-gemma-3-1b.yaml

echo "### Deploy Inference Model for gemma 3 1b"
kubectl apply -f im-gemma-3-1b-ft.yaml
