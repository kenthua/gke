#!/bin/bash

# https://cloud.google.com/trace/docs/setup/nodejs
# https://github.com/GoogleCloudPlatform/cloud-trace-nodejs

export PROJECT_ID=kenthua-testing
gcloud container clusters create trace-cluster --scopes https://www.googleapis.com/auth/trace.append

##
docker build -t gcr.io/$PROJECT_ID/node-app:v1 .
gcloud docker -- push gcr.io/$PROJECT_ID/node-app:v1
######
##OR##
######
gcloud container builds submit --config cloudbuild.yaml .
##
kubectl delete deployment node-web
kubectl run node-web --image=gcr.io/$PROJECT_ID/node-app:v1 --port 8080 --image-pull-policy Always
kubectl expose deployment node-web --type=LoadBalancer --port 80 --target-port 8080
