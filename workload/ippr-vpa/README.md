# In-Place Pod Resizing example
Extension of the [whereami workload example](https://github.com/GoogleCloudPlatform/kubernetes-engine-samples/tree/main/quickstarts/whereami/k8s)

## Core
```
kubectl kustomize | kubectl apply -f -
```

## Automated 
Through VPA `vpa.yaml`. Only allow resizing of CPU, otherwise we set restart for memory.

## Manual
Through `resize.sh` at the pod level. The controller will reset this eventually.