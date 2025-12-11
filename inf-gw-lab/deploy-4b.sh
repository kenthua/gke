#!/bin/bash

DEPLOY_TYPE=$(echo "$1" | tr '[:upper:]' '[:lower:]')

if [ "$DEPLOY_TYPE" != "tpu" ] && [ "$DEPLOY_TYPE" != "gpu" ]; then
  DEPLOY_TYPE="gpu"
fi

echo "### Deploy gemma 3 4b"
if [ "$DEPLOY_TYPE" = "gpu" ]; then
  kubectl apply -f gemma-3-4b.yaml
else
  kubectl apply -f tpu-gemma-3-4b.yaml
fi

echo "### Deploy Inference Pool for gemma 3 1b"
INFERENCE_POOL=vllm-gemma-3-4b
helm install ${INFERENCE_POOL} \
  --set inferencePool.modelServers.matchLabels.app=vllm-gemma-3-4b \
  --set provider.name=gke \
  --version v1.0.1 \
  oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool \
  -f epp-values.yaml

echo "### Deploy Inference Objective for gemma 3 4b"
kubectl apply -f io-gemma-3-4b.yaml

echo "### Deploy HTTPRoute for gemma 3 4b"
kubectl apply -f hr-gemma-3-4b.yaml
