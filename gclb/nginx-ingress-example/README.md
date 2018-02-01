### ingress-nginx on GKE

### Sources
* [Overview and install](https://github.com/kubernetes/ingress-nginx)
* [Annotations](https://github.com/kubernetes/ingress-gce/blob/master/docs/annotations.md)


Setup helm if necessary

```
kubectl create serviceaccount -n kube-system tiller
kubectl create clusterrolebinding tiller-binding     --clusterrole=cluster-admin     --serviceaccount kube-system:tiller
helm init --service-account tiller
```

Setup ingress-nginx via helm with release name `a`
```
helm install stable/nginx-ingress --name a
```

Replace the original nginx-ingress-controller service with a modified one to use TCP L4 internal IP
```
kubectl delete svc a-nginx-ingress-controller
kubectl apply -f nginx-controller-service.yaml.yaml
```

Patch ingress-nginx deployment with gce/gke parameter publish service 
```
kubectl patch deployment a-nginx-ingress-controller --type='json' --patch="$(cat publish-service-patch.yaml )"
```

Install a sample app
```
kubectl apply -f https://raw.githubusercontent.com/ahmetb/gke-letsencrypt/master/yaml/sample-app.yaml
```

Apply the nginx ingress manifest for helloweb
```
kubectl apply -f helloweb-ingress.yaml
```

