#!/bin/bash

echo "### Deploy gemma 3 4b"
kubectl apply -f gemma-3-4b.yaml

echo "### Deploy Inference Pool for gemma 3 1b"
INFERENCE_POOL=vllm-gemma-3-4b
helm install ${INFERENCE_POOL} \
  --set inferencePool.modelServers.matchLabels.app=vllm-gemma-3-4b \
  --set provider.name=gke \
  --version v0.3.0 \
  oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool

echo "### Deploy Inference Model for gemma 3 4b"
kubectl apply -f im-gemma-3-4b.yaml

echo "### Deploy HTTPRoute for gemma 3 4b"
kubectl apply -f hr-gemma-3-4b.yaml
