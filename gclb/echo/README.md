### GKE with HTTPS Ingress, secret managed certificate for L7 LB
The app echo contains the certificate in the container image

```
kubectl apply -f gcp-secret-tls.yaml
kubectl apply -f app.yaml
```
