#!/bin/bash

echo "### Set env"
export PROJECT_ID=$(gcloud config get-value project)
export MODEL_ARMOR_TEMPLATE_NAME=llm
export MODEL=google/gemma-3-1b-it
export CLUSTER_NAME=vllm-inference
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format 'get(projectNumber)')
export LOCATION=$(gcloud compute project-info describe \
--format="value(commonInstanceMetadata.items[google-compute-default-region])")

echo "### Enable model armor API"
gcloud services enable modelarmor.googleapis.com --quiet

echo "### Sleep 30s for model armor API"
sleep 30

echo "### Set default model armor API location"
gcloud config set api_endpoint_overrides/modelarmor \
"https://modelarmor.$LOCATION.rep.googleapis.com/"

echo "### Create model armor template"
gcloud model-armor templates create $MODEL_ARMOR_TEMPLATE_NAME --location $LOCATION \
  --pi-and-jailbreak-filter-settings-enforcement=enabled \
  --pi-and-jailbreak-filter-settings-confidence-level=MEDIUM_AND_ABOVE \
  --rai-settings-filters='[{ "filterType": "HATE_SPEECH", "confidenceLevel": "MEDIUM_AND_ABOVE" },{ "filterType": "DANGEROUS", "confidenceLevel": "MEDIUM_AND_ABOVE" },{ "filterType": "HARASSMENT", "confidenceLevel": "MEDIUM_AND_ABOVE" },{ "filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": "MEDIUM_AND_ABOVE" }]' \
  --template-metadata-log-sanitize-operations \
  --template-metadata-log-operations

echo "### Set permissions for model armor"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:service-$PROJECT_NUMBER@gcp-sa-dep.iam.gserviceaccount.com \
    --role=roles/container.admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:service-$PROJECT_NUMBER@gcp-sa-dep.iam.gserviceaccount.com \
    --role=roles/modelarmor.calloutUser
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:service-$PROJECT_NUMBER@gcp-sa-dep.iam.gserviceaccount.com \
    --role=roles/serviceusage.serviceUsageConsumer
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:service-$PROJECT_NUMBER@gcp-sa-dep.iam.gserviceaccount.com \
    --role=roles/modelarmor.user

echo "### Deploy GCP Traffic Extension"
envsubst < gte-gateway.yaml.tmpl > gte-gateway.yaml
kubectl apply -f gte-gateway.yaml
