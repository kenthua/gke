#!/bin/bash

gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable networkservices.googleapis.com

export PROJECT_ID=$(gcloud config get-value project)
export REGION=$(gcloud compute project-info describe \
    --format="value(commonInstanceMetadata.items[google-compute-default-region])")

export CLUSTER_NAME=vllm-inference
export NETWORK=default
export SUBNET=default

gcloud compute networks subnets create $REGION-proxy-only-subnet \
    --purpose=REGIONAL_MANAGED_PROXY \
    --role=ACTIVE \
    --region=$REGION \
    --network=$NETWORK \
    --range=10.0.200.0/23

gcloud container clusters create-auto $CLUSTER_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --network=$NETWORK \
    --subnetwork=$SUBNET \
    --release-channel=rapid \
    --auto-monitoring-scope=ALL

kubectl apply -f https://github.com/kubernetes-sigs/gateway-api-inference-extension/releases/download/v1.0.0/manifests.yaml

kubectl apply -f inference-gateway-metrics-rbac.yaml

kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/k8s-stackdriver/master/custom-metrics-stackdriver-adapter/deploy/production/adapter_new_resource_model.yaml

PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format 'get(projectNumber)')

gcloud projects add-iam-policy-binding projects/$PROJECT_ID \
    --role roles/monitoring.viewer \
    --member=principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$PROJECT_ID.svc.id.goog/subject/ns/custom-metrics/sa/custom-metrics-stackdriver-adapter
