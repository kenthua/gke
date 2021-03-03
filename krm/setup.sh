export PROJECT_ID=kenthua-test-standalone
export CC_SA=cc-cnrm-system
export CLUSTER_NAME=release-k8s
export CLUSTER_LOCATION=us-central1-c
export NAMESPACE=${PROJECT_ID}

## cc tool
# https://cloud.google.com/config-connector/docs/how-to/import-export/overview#installing-config-connector
gsutil cp gs://cnrm/latest/cli.tar.gz .
tar zxf cli.tar.gz
chmod 755 linux/amd64/config-connector
mv linux/amd64/config-connector ~/.local/bin
gcloud services enable cloudasset.googleapis.com


gcloud container clusters create ${CLUSTER_NAME} \
    --release-channel regular \
    --addons ConfigConnector \
    --workload-pool=${PROJECT_ID}.svc.id.goog \
    --enable-stackdriver-kubernetes \
    --zone ${CLUSTER_LOCATION}

gcloud container node-pools update default-pool --workload-metadata=GKE_METADATA \
  --cluster ${CLUSTER_NAME} \
  --zone ${CLUSTER_LOCATION}

gcloud container clusters update ${CLUSTER_NAME} \
  --update-addons ConfigConnector=ENABLED \
  --zone ${CLUSTER_ZONE}

# iam
gcloud iam service-accounts create cc-cnrm-system

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${CC_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/owner"

gcloud iam service-accounts add-iam-policy-binding \
${CC_SA}@${PROJECT_ID}.iam.gserviceaccount.com \
    --member="serviceAccount:${PROJECT_ID}.svc.id.goog[cnrm-system/cnrm-controller-manager]" \
    --role="roles/iam.workloadIdentityUser"

# install CC resource
cat <<EOF > configconnector.yaml
apiVersion: core.cnrm.cloud.google.com/v1beta1
kind: ConfigConnector
metadata:
  # the name is restricted to ensure that there is only one
  # ConfigConnector resource installed in your cluster
  name: configconnector.core.cnrm.cloud.google.com
spec:
  mode: cluster
  googleServiceAccount: "${CC_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
EOF
k apply -f configconnector.yaml

# prepare resource namespace
kubectl create namespace ${NAMESPACE}
kubectl annotate namespace \
  ${NAMESPACE} \
  cnrm.cloud.google.com/project-id=${PROJECT_ID}

# Resources
# https://cloud.google.com/config-connector/docs/reference/resource-docs/container/containercluster
k apply -f resources/vpc.yaml -n ${NAMESPACE}
k apply -f resources/gke-cluster.yaml -n ${NAMESPACE}
k apply -f resources/gke-nodepool.yaml -n ${NAMESPACE}