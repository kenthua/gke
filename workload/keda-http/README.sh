# KEDA and scale to 0 on a simple app with Gateway

- Enable Gateway on the cluster if it is not already there
```sh
gcloud container clusters update cluster-std --location=us-central1 --gateway-api=standard
```

- Install keda
```sh
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
```

```sh
helm install keda kedacore/keda --namespace keda --create-namespace
```

- Install keda http addon
```sh
helm install http-add-on kedacore/keda-add-ons-http --namespace keda
```

- Deploy workload
```sh
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

- Deploy Keda HTTP object
This will create 2 HPA objects, one for the interceptor, which is the proxy that keda listens for traffic and the HPA for your deployment

```sh
kubectl apply -f httpscaledobject.yaml
```

```sh
kubectl get hpa
NAME             REFERENCE          TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
keda-hpa-hello   Deployment/hello   0/100 (avg)   1         2         1          4m21s

kubectl get hpa -n keda
NAME                                     REFERENCE                                  TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
keda-hpa-keda-add-ons-http-interceptor   Deployment/keda-add-ons-http-interceptor   0/200 (avg)   3         50        3          4m23s
```

- Deploy Gateway objects
```sh
kubectl apply -f gateway.yaml
kubectl apply -f httproute.yaml
```

- External curl on xlb or use sleep from istio pod for curl within the cluster
```sh
kubectl apply -f https://raw.githubusercontent.com/istio/istio/refs/heads/master/samples/sleep/sleep.yaml

export GW_IP=$(kubectl get gateway/vllm-ilb \
  -o jsonpath='{.status.addresses[0].value}')
export GW_PORT=80

SLEEP_POD=$(kubectl get pod -l app=sleep --no-headers -o custom-columns=":metadata.name")
kubectl exec $SLEEP_POD -- curl -H "Host: hello.app" http://$GW_IP:$GW_PORT
```

- After about ~5 min based on the settings of no traffic, the deployment hello will scale down to 0
The keda operator will have this log entry, triggering a scale down to 0
```
2025-10-03T22:32:14Z    INFO    scaleexecutor   Successfully set ScaleTarget replicas count to ScaledObject minReplicaCount     {"scaledobject.Name": "hello", "scaledObject.Namespace": "default", "scaleTarget.Name": "hello", "Original Replicas Count": 1, "New Replicas Count": 0}
```