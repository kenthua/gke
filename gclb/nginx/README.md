### GKE with HTTPS Ingress, secret managed certificate for L7 LB
The nginx app references the certificates from the secret

```
kubectl apply -f gcp-secret-tls.yaml
kubectl apply -f nginx-secret-tls.yaml
kubectl apply -f nginx-secure-app.yaml
kubectl apply -f nginx-service.yaml
kubectl apply -f nginx-ingress.yaml
```

### GKE with HTTPS Ingress via GCP managed certificate for L7 LB
The nginx app references the certificates from the secret

```
gcloud compute ssl-certificates create test-cert --certificate=ssl/gcp-tls.crt
--private-key=ssl/gcp-tls.key --project=$PROJECT_ID
kubectl apply -f nginx-secret-tls.yaml
kubectl apply -f nginx-secure-app.yaml
kubectl apply -f nginx-service.yaml
kubectl apply -f nginx-ingress-external-cert.yaml
```

### GKE with Internal TCP Load balancer L4 LB
The nginx app references the certificates from the secret

```
kubectl apply -f nginx-secret-tls.yaml
kubectl apply -f nginx-secure-app.yaml
kubectl apply -f nginx-service-internal.yaml
```

