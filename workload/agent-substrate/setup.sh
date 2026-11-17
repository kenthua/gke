#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# setup.sh: Setup Agent Substrate with GKE ComputeClass on cluster-std

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Source environment variables
source "${SCRIPT_DIR}/ate-dev-env.sh"

echo "============================================================"
echo "Agent Substrate Setup on GKE with ComputeClass (${SUBSTRATE_COMPUTE_CLASS})"
echo "Project:  ${PROJECT_ID}"
echo "Cluster:  ${CLUSTER_NAME} (${GCE_REGION})"
echo "Context:  ${KUBECTL_CONTEXT}"
echo "============================================================"

# Verify cluster connectivity
echo "==> Verifying kubectl connectivity..."
kubectl cluster-info >/dev/null

# 2. Apply ComputeClass (substituting ${NODE_SA_EMAIL} from ate-dev-env.sh / .env)
echo "==> Applying ComputeClass: ${SUBSTRATE_COMPUTE_CLASS}..."
envsubst < "${SCRIPT_DIR}/substrate-computeclass.yaml" | kubectl apply -f -
kubectl get computeclass "${SUBSTRATE_COMPUTE_CLASS}"

# 3. Create & Label ate-system Namespace
echo "==> Preparing ate-system namespace with default ComputeClass..."
kubectl apply -f "${SCRIPT_DIR}/ate-system-namespace.yaml"
kubectl get namespace ate-system --show-labels

# 4. Apply Agent Substrate CRDs
echo "==> Applying Agent Substrate CRDs..."
kubectl apply -f "${SCRIPT_DIR}/crds/"

# 5. Ensure GCS Snapshot & Asset Buckets exist
echo "==> Checking GCS snapshot bucket (gs://${BUCKET_NAME})..."
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Creating snapshot bucket gs://${BUCKET_NAME}..."
    gcloud storage buckets create "gs://${BUCKET_NAME}" \
        --project="${PROJECT_ID}" \
        --location="${GCE_REGION}" \
        --uniform-bucket-level-access
else
    echo "Snapshot bucket gs://${BUCKET_NAME} already exists."
fi

ASSETS_BUCKET="${BUCKET_NAME}-assets"
echo "==> Checking GCS assets bucket (gs://${ASSETS_BUCKET})..."
if ! gcloud storage buckets describe "gs://${ASSETS_BUCKET}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Creating micro-VM assets bucket gs://${ASSETS_BUCKET}..."
    gcloud storage buckets create "gs://${ASSETS_BUCKET}" \
        --project="${PROJECT_ID}" \
        --location="${GCE_REGION}" \
        --uniform-bucket-level-access
else
    echo "Assets bucket gs://${ASSETS_BUCKET} already exists."
fi

# 6. Apply SandboxConfigs (gVisor default)
echo "==> Applying gVisor SandboxConfig..."
kubectl apply -f "${SCRIPT_DIR}/sandboxconfig-gvisor.yaml"

# 7. Apply WorkerPools (gVisor & MicroVM targeting ComputeClass)
echo "==> Applying WorkerPool manifests..."
kubectl apply -f "${SCRIPT_DIR}/workerpool-gvisor.yaml"
kubectl apply -f "${SCRIPT_DIR}/workerpool-microvm.yaml"

# 8. Configure IAM for Snapshot Transfer & Asset Access
echo "==> Configuring IAM Service Accounts and GCS permissions..."
if ! gcloud iam service-accounts describe "${SNAPSHOT_TRANSFER_SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Creating snapshot transfer service account..."
    gcloud iam service-accounts create "${SNAPSHOT_TRANSFER_GSA_NAME}" \
        --project="${PROJECT_ID}" \
        --display-name="Agent Substrate Snapshot Transfer SA"
else
    echo "Snapshot transfer service account ${SNAPSHOT_TRANSFER_GSA_NAME} already exists."
fi

# Grant Token Creator to ate-api-server principal
WI_API_SERVER="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/ate-system/sa/ate-api-server"
WI_ATELET="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/ate-system/sa/atelet"

echo "Binding IAM permissions for Workload Identity & GCS buckets..."
gcloud iam service-accounts add-iam-policy-binding "${SNAPSHOT_TRANSFER_SA_EMAIL}" \
    --project="${PROJECT_ID}" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --member="${WI_API_SERVER}" >/dev/null 2>&1 || true

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
    --member="${WI_API_SERVER}" \
    --role="roles/storage.objectAdmin" >/dev/null 2>&1 || true
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
    --member="serviceAccount:${SNAPSHOT_TRANSFER_SA_EMAIL}" \
    --role="roles/storage.objectAdmin" >/dev/null 2>&1 || true
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
    --member="${WI_ATELET}" \
    --role="roles/storage.objectAdmin" >/dev/null 2>&1 || true
gcloud storage buckets add-iam-policy-binding "gs://${ASSETS_BUCKET}" \
    --member="${WI_ATELET}" \
    --role="roles/storage.objectViewer" >/dev/null 2>&1 || true

echo ""
echo "============================================================"
echo "Agent Substrate Foundation Applied Successfully!"
echo "============================================================"
echo "WorkerPools status:"
kubectl get workerpools -A || true
echo ""
echo "Next step: Deploy the Agent Substrate control plane into ate-system:"
echo "  go run ./cmd/ate-setup deploy ate-system \\"
echo "    --image-repo=${ATE_IMAGE_REPO} \\"
echo "    --image-tag=${ATE_IMAGE_TAG} \\"
echo "    --credential-provider='${ATE_CREDENTIAL_PROVIDER}' \\"
echo "    --ingress-allowed-spiffe-ids='${ATE_INGRESS_ALLOWED_SPIFFE_IDS}' \\"
echo "    --snapshot-location='${SNAPSHOT_LOCATION}' \\"
echo "    --snapshot-transfer-gsa-name='${SNAPSHOT_TRANSFER_GSA_NAME}' \\"
echo "    --storage-bucket-name='${BUCKET_NAME}' \\"
echo "    --gcp-project-id='${PROJECT_ID}' \\"
echo "    --gcp-cluster-name='${CLUSTER_NAME}' \\"
echo "    --gcp-cluster-location='${CLUSTER_LOCATION}'"
echo "============================================================"
