# Stackdriver Trace sample for Node.js

### Sources
https://cloud.google.com/trace/docs/setup/nodejs

https://github.com/GoogleCloudPlatform/cloud-trace-nodejs

### Start

```
cd tf
terraform plan
terrfaorm apply
```

or manually,

```
export PROJECT_ID=$PROJECT_ID
gcloud container clusters create trace-cluster --scopes https://www.googleapis.com/auth/trace.append
```

### Build the container image

```
gcloud container builds submit --config cloudbuild.yaml .

```

or manually,

```
docker build -t gcr.io/$PROJECT_ID/node-app:v1 .
gcloud docker -- push gcr.io/$PROJECT_ID/node-app:v1
```

### Deployment

Generate configs appropriate for your environment

```
kubectl run node-web --image=gcr.io/$PROJECT_ID/node-app:v1 --port 8080 --image-pull-policy Always --dry-run -o yaml > k8s/deployment.yaml
kubectl expose deployment node-web --type=LoadBalancer --port 80 --target-port 8080 --dry-run -o yaml > k8s/service.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

or modify the existing files and apply

```
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

Delete if necessary

```
kubectl delete deployment node-web
```

### Bonus: Tagging versions in GCR

```
gcloud container images add-tag gcr.io/$PROJECT_ID/node-app:v1 gcr.io/$PROJECT_ID/node-app:v1.1
```

Edit patch.yaml accordingly

```
kubectl patch --local -o yaml -f k8s/deployment.yaml -p "$(cat patch.yaml)" > k8s/deployment.yaml
kubectl apply -f k8s/deployment.yaml
```
