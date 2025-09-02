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
export MODEL_PATH=
export BUCKET=$PROJECT_ID

echo "### Get cluster"
gcloud container clusters get-credentials $CLUSTER_NAME \
--region $REGION \
--project $PROJECT_ID

echo "### Deploy TPU Compute Class for v5e->v6e"
if [ "$DEPLOY_TYPE" = "tpu" ]; then
  kubectl apply -f tpu-cc.yaml
fi

echo "### Deploy gemma 3 1b fine-tuned"
if [ "$DEPLOY_TYPE" = "gpu" ]; then
  envsubst < gemma-3-1b-ft.yaml.tmpl > gemma-3-1b-ft.yaml
  kubectl apply -f gemma-3-1b-ft.yaml
else
  envsubst < tpu-gemma-3-1b-ft.yaml.tmpl > tpu-gemma-3-1b-ft.yaml
  kubectl apply -f tpu-gemma-3-1b-ft.yaml
fi

echo "### Deploy HTTPRoute for gemma 3 1b FT"
envsubst < hr-gemma-3-1b-ft.yaml.tmpl > hr-gemma-3-1b-ft.yaml
kubectl apply -f hr-gemma-3-1b-ft.yaml

echo "### Deploy Inference Pool for gemma 3 1b fine-tuned"
INFERENCE_POOL=vllm-gemma-3-1b-ft
helm install ${INFERENCE_POOL} \
  --set inferencePool.modelServers.matchLabels.app=vllm-gemma-3-1b-ft \
  --set provider.name=gke \
  --version v0.5.1 \
  --set inferenceExtension.replicas=2 \
  oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool \
  -f epp-values.yaml

echo "### Deploy Inference Model for gemma 3 1b fine-tuned"
envsubst < im-gemma-3-1b-ft.yaml.tmpl > im-gemma-3-1b-ft.yaml
kubectl apply -f im-gemma-3-1b-ft.yaml
