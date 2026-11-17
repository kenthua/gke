#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Environment configuration for Agent Substrate on GKE (cluster-std)
# Sourced by setup scripts, tools/setup-gcp, and ate-setup.
# Automatically loads local overrides from .env if present.

_ATE_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${_ATE_ENV_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${_ATE_ENV_DIR}/.env"
    set +a
fi

export PROJECT_ID="${PROJECT_ID:-YOUR_PROJECT_ID}"
export PROJECT_NUMBER="${PROJECT_NUMBER:-YOUR_PROJECT_NUMBER}"

export GCE_REGION="${GCE_REGION:-us-central1}"
export CLUSTER_LOCATION="${CLUSTER_LOCATION:-us-central1}"
export CLUSTER_NAME="${CLUSTER_NAME:-cluster-std}"

export KUBECTL_CONTEXT="gke_${PROJECT_ID}_${GCE_REGION}_${CLUSTER_NAME}"

# Snapshot storage bucket configuration
export BUCKET_NAME="${BUCKET_NAME:-agent-substrate-snapshots-${PROJECT_ID}}"
export SNAPSHOT_LOCATION="gs://${BUCKET_NAME}/"
export SNAPSHOT_TRANSFER_GSA_NAME="${SNAPSHOT_TRANSFER_GSA_NAME:-ate-snapshot-transfer}"

# GKE Node & Snapshot Transfer Service Accounts
export NODE_GSA_NAME="${NODE_GSA_NAME:-minimal-node}"
export IAM_GSA_DOMAIN="${IAM_GSA_DOMAIN:-iam.gserviceaccount.com}"
export NODE_SA_EMAIL="${NODE_SA_EMAIL:-${NODE_GSA_NAME}@${PROJECT_ID}.${IAM_GSA_DOMAIN}}"
export SNAPSHOT_TRANSFER_SA_EMAIL="${SNAPSHOT_TRANSFER_SA_EMAIL:-${SNAPSHOT_TRANSFER_GSA_NAME}@${PROJECT_ID}.${IAM_GSA_DOMAIN}}"

# Hardware / Virtualization
export ENABLE_NESTED_VIRTUALIZATION=true

# Sandbox classes to support (gVisor syscall sandbox & microVM hardware virtualization)
export ATE_INSTALL_SANDBOX_CLASSES="gvisor,microvm"

# SPIFFE IDs allowed to reach actors through atenet Envoy router
export ATE_INGRESS_ALLOWED_SPIFFE_IDS="spiffe://cluster.local/ns/default/sa/default,spiffe://cluster.local/ns/ate-demo-counter/sa/default,spiffe://cluster.local/ns/ate-system/sa/atenet-client"

# Credential provider for egress credential injection
export ATE_CREDENTIAL_PROVIDER='{"name":"k8s.io"}'

# Upstream image repository and release tag
export ATE_IMAGE_REPO="ghcr.io/agent-substrate/substrate"
export ATE_IMAGE_TAG="v1.0.0"

# GKE ComputeClass name
export SUBSTRATE_COMPUTE_CLASS="substrate-n2"
