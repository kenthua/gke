#!/bin/bash

echo "### Set env"
PROJECT_ID=$GOOGLE_CLOUD_PROJECT
LOCATION=$(gcloud compute project-info describe \
--format="value(commonInstanceMetadata.items[google-compute-default-region])")

echo "### Create Cloud Armor security policy"
gcloud compute security-policies create allow-users-policy \
  --description "policy for only allowing users" \
  --region $LOCATION

echo "### Update the deny rule"
gcloud compute security-policies rules update 2147483647 \
  --security-policy allow-users-policy \
  --action "deny-all-404" \
  --region $LOCATION

echo "### Create the allow rule"
gcloud compute security-policies rules create 1000 \
  --security-policy allow-users-policy \
  --expression "has(request.headers['user-id'])" \
  --action "allow" \
  --description "require header" \
  --region $LOCATION

echo "### Patch the GCPBackendPolicy"
kubectl patch gcpbackendpolicy vllm-gemma-3-1b \
  --type merge \
  --patch-file patch.yaml
