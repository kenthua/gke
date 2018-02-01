### ingress-nginx on GKE

### Sources
* [Overview and install](https://github.com/kubernetes/ingress-nginx)
* [Annotations nginx](https://github.com/kubernetes/ingress-nginx/blob/master/docs/user-guide/annotations.md)
* [Annotations GCP](https://github.com/kubernetes/ingress-gce/blob/master/docs/annotations.md)


Pre-reqs
```
curl https://raw.githubusercontent.com/kubernetes/ingress-nginx/master/deploy/namespace.yaml \
    | kubectl apply -f -

curl https://raw.githubusercontent.com/kubernetes/ingress-nginx/master/deploy/default-backend.yaml \
    | kubectl apply -f -

curl https://raw.githubusercontent.com/kubernetes/ingress-nginx/master/deploy/configmap.yaml \
    | kubectl apply -f -

curl https://raw.githubusercontent.com/kubernetes/ingress-nginx/master/deploy/tcp-services-configmap.yaml \
    | kubectl apply -f -

curl https://raw.githubusercontent.com/kubernetes/ingress-nginx/master/deploy/udp-services-configmap.yaml \
    | kubectl apply -f -
```

Apply the service

```
kubectl apply -f ingress-nginx-service.yaml
```

Apply the deployment

```
kubectl apply -f ingress-nginx-deployment.yaml
```

Install a sample app
```
kubectl apply -f https://raw.githubusercontent.com/ahmetb/gke-letsencrypt/master/yaml/sample-app.yaml
```

Apply the nginx ingress manifest for helloweb
```
kubectl apply -f helloweb-ingress.yaml
```

