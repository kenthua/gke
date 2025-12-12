# Pod Snapshotting
https://docs.cloud.google.com/kubernetes-engine/docs/how-to/pod-snapshots

# Enable it in the cluster
```
export PROJECT_ID=
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID \
  --format 'get(projectNumber)')
export CLUSTER_NAME=cluster-std
export LOCATION=us-central1
export SNAPSHOT_BUCKET_NAME=$PROJECT_ID-snap
export SNAPSHOT_BUCKET_LOCATION=$LOCATION
export KSA=snapshotting
export NAMESPACE=snapshotting
export APP_LABEL=vllm-gemma-3-1b-it
export MODEL_BUCKET=$PROJECT_ID
export MODEL_ID=google/gemma-3-1b-it
export HF_TOKEN=
```

```
gcloud beta container clusters update $CLUSTER_NAME \
   --location $LOCATION \
   --enable-pod-snapshots

gcloud container node-pools create g2-standard-8-sbx \
  --cluster=$CLUSTER_NAME \
  --location=$LOCATION \
  --node-locations=us-central1-a,us-central1-b,us-central1-c \
  --machine-type=g2-standard-8 \
  --image-type=cos_containerd \
  --sandbox type=gvisor \
  --spot \
  --enable-autoscaling \
  --num-nodes 0 \
  --min-nodes 0 \
  --max-nodes 10

gcloud container node-pools update g2-standard-8-sbx \
    --cluster=$CLUSTER_NAME \
    --location=$LOCATION \
    --node-labels="cloud.google.com/compute-class=l4-gpu-cc"

gcloud container node-pools update g2-standard-8-sbx \
    --cluster=$CLUSTER_NAME \
    --location=$LOCATION \
    --node-taints="cloud.google.com/compute-class=l4-gpu-cc:NoSchedule"
```

```
kubectl create secret generic hf-secret \
--from-literal=hf_api_token=$HF_TOKEN \
--dry-run=client -o yaml | kubectl apply -n $NAMESPACE -f -
```

```
gcloud storage buckets create "gs://$SNAPSHOT_BUCKET_NAME" \
   --uniform-bucket-level-access \
   --enable-hierarchical-namespace \
   --soft-delete-duration=0d \
   --location="$LOCATION"

gcloud storage buckets add-iam-policy-binding "gs://$SNAPSHOT_BUCKET_NAME" \
    --member="principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$PROJECT_ID.svc.id.goog/subject/ns/$NAMESPACE/sa/$KSA" \
    --role="roles/storage.bucketViewer"

gcloud storage buckets add-iam-policy-binding "gs://$SNAPSHOT_BUCKET_NAME" \
    --member="principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$PROJECT_ID.svc.id.goog/subject/ns/$NAMESPACE/sa/$KSA" \
    --role="roles/storage.objectUser"

gcloud iam roles create podSnapshotGcsReadWriter \
    --project="$PROJECT_ID" \
    --permissions="storage.objects.get,storage.objects.create,storage.objects.delete,storage.folders.create"

gcloud storage buckets add-iam-policy-binding "gs://$SNAPSHOT_BUCKET_NAME" \
    --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$PROJECT_ID.svc.id.goog/namespace/$NAMESPACE" \
    --role="roles/storage.bucketViewer"

gcloud storage managed-folders create "gs://$SNAPSHOT_BUCKET_NAME/snapshot-1/"

gcloud storage managed-folders add-iam-policy-binding "gs://$SNAPSHOT_BUCKET_NAME/snapshot-1/" \
    --member="principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$PROJECT_ID.svc.id.goog/subject/ns/$NAMESPACE/sa/$KSA" \
    --role="projects/$PROJECT_ID/roles/podSnapshotGcsReadWriter"

kubectl create namespace $NAMESPACE
kubectl create serviceaccount $KSA \
    --namespace $NAMESPACE
```

## Configure snapshots
```
envsubst < podsnapshot-storage-config.yaml.tmpl > podsnapshot-storage-config.yaml
kubectl apply -n $NAMESPACE -f podsnapshot-storage-config.yaml

envsubst < podsnapshot-policy.yaml.tmpl > podsnapshot-policy.yaml
kubectl apply -n $NAMESPACE -f podsnapshot-policy.yaml
```

## Download the model and store in GCS
```
gcloud storage buckets create "gs://$MODEL_BUCKET" \
   --uniform-bucket-level-access \
   --enable-hierarchical-namespace \
   --location="$LOCATION"

gcloud storage buckets add-iam-policy-binding "gs://$MODEL_BUCKET" \
    --member="principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$PROJECT_ID.svc.id.goog/subject/ns/$NAMESPACE/sa/$KSA" \
    --role="roles/storage.objectUser"


envsubst < model-download.yaml.tmpl > model-download.yaml
kubectl apply -n $NAMESPACE -f model-download.yaml
```

## Deploy the model
```
envsubst < gemma-3-1b-it.runai.yaml.tmpl > gemma-3-1b-it.runai.yaml
kubectl apply -n $NAMESPACE -f gemma-3-1b-it.runai.yaml
```

## Scale the model