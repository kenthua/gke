#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Quickstart script demonstrating how an AI agent can leverage Agent Substrate
# MicroVM actors for fast, secure, isolated sandbox execution.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ATESPACE="default"
TEMPLATE="microvm-actor-template"
ACTOR_NAME="agent-sandbox-$(date +%s)"
# Pick an available random local port
LOCAL_PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
CONTAINER_PORT=8080

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}        Agent Substrate: MicroVM Actor Lifecycle Demo           ${NC}"
echo -e "${BLUE}================================================================${NC}"
echo -e "Atespace:       ${GREEN}${ATESPACE}${NC}"
echo -e "Actor Template: ${GREEN}${TEMPLATE}${NC}"
echo -e "Sandbox Actor:  ${GREEN}${ACTOR_NAME}${NC}"
echo ""

cleanup() {
    echo ""
    echo -e "${YELLOW}>>> Cleaning up resources...${NC}"
    if [ -n "${PROXY_PID:-}" ] && kill -0 "$PROXY_PID" 2>/dev/null; then
        kill "$PROXY_PID" 2>/dev/null || true
    fi
    echo -e "Deleting actor ${ACTOR_NAME}..."
    kubectl ate delete actor "${ACTOR_NAME}" -a "${ATESPACE}" 2>/dev/null || true
    echo -e "${GREEN}Cleanup complete.${NC}"
}
trap cleanup EXIT

# 1. Check if ActorTemplate exists
echo -e "${BLUE}[Step 1/5] Checking ActorTemplate status...${NC}"
kubectl ate get actor-template "${TEMPLATE}" -a "${ATESPACE}"
echo ""

# 2. Create the Actor from the Golden Snapshot Template
echo -e "${BLUE}[Step 2/5] Creating Actor instance from golden snapshot...${NC}"
kubectl ate create actor "${ACTOR_NAME}" -a "${ATESPACE}" --template "${TEMPLATE}"
echo ""

# 3. Resume the Actor (Cold-Start / Snapshot Restore into Cloud Hypervisor)
echo -e "${BLUE}[Step 3/5] Resuming Actor into MicroVM sandbox...${NC}"
START_TIME=$(date +%s%N)
kubectl ate resume actor "${ACTOR_NAME}" -a "${ATESPACE}"
END_TIME=$(date +%s%N)
DIFF_MS=$(( (END_TIME - START_TIME) / 1000000 ))
echo -e "${GREEN}✓ Actor resumed and running in ${DIFF_MS} ms!${NC}"
echo ""

# 4. Proxy and execute request against the Actor Sandbox
echo -e "${BLUE}[Step 4/5] Establishing secure proxy tunnel and querying sandbox...${NC}"
PROXY_LOG=$(mktemp)
kubectl ate proxy actor "${ACTOR_NAME}" "${LOCAL_PORT}:${CONTAINER_PORT}" -a "${ATESPACE}" >"$PROXY_LOG" 2>&1 &
PROXY_PID=$!

# Wait for proxy socket to become available
for i in {1..50}; do
    if curl -s "http://127.0.0.1:${LOCAL_PORT}/" >/dev/null 2>&1; then
        break
    fi
    sleep 0.1
done

echo -e "Sending request to Actor inside MicroVM (http://127.0.0.1:${LOCAL_PORT}/)..."
RESPONSE=$(curl -s "http://127.0.0.1:${LOCAL_PORT}/")
echo -e "${GREEN}Response from Actor Sandbox:${NC}"
echo "${RESPONSE}"
echo ""

# 5. Suspend the Actor (Snapshot & Memory Release)
echo -e "${BLUE}[Step 5/5] Suspending Actor to release CPU & RAM back to cluster...${NC}"
START_SUSPEND=$(date +%s%N)
kubectl ate suspend actor "${ACTOR_NAME}" -a "${ATESPACE}"
END_SUSPEND=$(date +%s%N)
SUSPEND_MS=$(( (END_SUSPEND - START_SUSPEND) / 1000000 ))
echo -e "${GREEN}✓ Actor suspended and state saved in ${SUSPEND_MS} ms!${NC}"
echo ""

echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}✓ Demo completed successfully!${NC}"
echo -e "Key Takeaway: The MicroVM actor booted in ~1s, served requests in hardware isolation, and suspended back to GCS memory snapshot."
echo -e "${BLUE}================================================================${NC}"
