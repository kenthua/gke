#!/bin/bash

# Default values
DEPLOY_TYPE="gpu"
FT_MODEL_PATH=""

# 1. Check if the first argument is a deployment type
LOWER_ARG_1=$(echo "$1" | tr '[:upper:]' '[:lower:]')
if [ "$LOWER_ARG_1" = "tpu" ] || [ "$LOWER_ARG_1" = "gpu" ]; then
  DEPLOY_TYPE="$LOWER_ARG_1"
  # If $1 is DEPLOY_TYPE, $2 MUST be FT_MODEL_PATH
  FT_MODEL_PATH="$2"
# 2. Otherwise, the first argument is assumed to be FT_MODEL_PATH
elif [ -n "$1" ]; then
  FT_MODEL_PATH="$1"
  # DEPLOY_TYPE remains the default "gpu"
fi

# --- Mandatory Path Check ---
if [ -z "$FT_MODEL_PATH" ]; then
  echo "❌ Error: FT_MODEL_PATH must be provided."
  echo "Usage: $0 <FT_MODEL_PATH>"
  echo "Usage: $0 <tpu|gpu> <FT_MODEL_PATH>"
  exit 1
fi

echo "### Set env"
export PROJECT_ID=$(gcloud config get-value project)
export CLUSTER_NAME=vllm-inference
export REGION=$(gcloud compute project-info describe \
  --format="value(commonInstanceMetadata.items[google-compute-default-region])")
export FT_MODEL_PATH=$1
export BUCKET=$PROJECT_ID

echo "### Get cluster"
gcloud container clusters get-credentials $CLUSTER_NAME \
--region $REGION \
--project $PROJECT_ID

if [ "$DEPLOY_TYPE" = "tpu" ]; then
  echo "### Deploy TPU Compute Class for v5e->v6e"
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
  --version v1.0.0 \
  oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool \
  -f epp-values.yaml

echo "### Deploy Inference Objective for gemma 3 1b fine-tuned"
envsubst < io-gemma-3-1b-ft.yaml.tmpl > io-gemma-3-1b-ft.yaml
kubectl apply -f io-gemma-3-1b-ft.yaml
