# Gateway + cert-manager + Google CAS

## Setup cert-manager
https://cert-manager.io/docs/installation/helm/

```shell
helm repo add jetstack https://charts.jetstack.io --force-update

helm install --create-namespace \
    --namespace cert-manager \
    --set installCRDs=true \
    --set global.leaderElection.namespace=cert-manager  \
    --set config.apiVersion="controller.config.cert-manager.io/v1alpha1"  \
    --set config.kind="ControllerConfiguration" \
    --set config.enableGatewayAPI=true \
    cert-manager jetstack/cert-manager
```

## Setup Google CAS
```shell
helm repo add jetstack https://charts.jetstack.io --force-update
helm upgrade -i cert-manager-google-cas-issuer jetstack/cert-manager-google-cas-issuer -n cert-manager --wait

# Workload Identity enabled GKE cluster
kubectl annotate serviceaccount \
    cert-manager-google-cas-issuer \
    iam.gke.io/gcp-service-account=sa-google-cas-issuer@${PROJECT:?PROJECT is not set}.iam.gserviceaccount.com \
    --namespace cert-manager \
    --overwrite=true
```

## Google CAS Issuer configuration
Config notes
https://cert-manager.io/docs/usage/gateway/

- Cluster Issuer
```shell
kubectl apply -f cas-cluster-issuer.yaml -n cert-manager
```

- Namespace Issuer
```shell
kubectl apply -f cas-issuer.yaml
```

## Gateway deployment
Deploys a regional internal L7 load balancer - `gke-l7-rilb`

- Cluster Issued
```shell
kubectl apply -f gateway.yaml
```

Sample log output of the cert-manager-google-cas-issuer
```shell
# GoogleCASIssuer log
I0424 00:46:53.874306       1 request_controller.go:178] "msg"="Request has not been approved or denied. Ignoring." "CertificateRequest"={"name":"whereami-example-com-tls-1","namespace":"default"} "controller"="certificaterequest" "controllerGroup"="cert-manager.io" "controllerKind"="CertificateRequest" "logger"="Reconcile" "name"="whereami-example-com-tls-1" "namespace"="default" "reconcileID"="2ea30a98-14e8-4635-a2a1-24607fb3a954"
I0424 00:46:54.003444       1 request_controller.go:229] "msg"="Initialised Ready condition" "CertificateRequest"={"name":"whereami-example-com-tls-1","namespace":"default"} "controller"="certificaterequest" "controllerGroup"="cert-manager.io" "controllerKind"="CertificateRequest" "logger"="Reconcile" "name"="whereami-example-com-tls-1" "namespace"="default" "reconcileID"="7af7a21e-6077-44c3-b5c2-bdc692a027aa"
I0424 00:46:54.308501       1 request_controller.go:274] "msg"="Successfully finished the reconciliation." "CertificateRequest"={"name":"whereami-example-com-tls-1","namespace":"default"} "controller"="certificaterequest" "controllerGroup"="cert-manager.io" "controllerKind"="CertificateRequest" "logger"="Reconcile" "name"="whereami-example-com-tls-1" "namespace"="default" "reconcileID"="589ea905-cf3e-4d16-8a40-e0c57a981fe6"
I0424 00:46:54.308730       1 recorder.go:104] "msg"="Succeeded signing the CertificateRequest" "logger"="events" "object"={"kind":"CertificateRequest","namespace":"default","name":"whereami-example-com-tls-1","uid":"15bcf222-f801-4a02-97aa-2e5a077f0778","apiVersion":"cert-manager.io/v1","resourceVersion":"1745455614053439000"} "reason"="Issued" "type"="Normal"

# Output
NAME                             CLASS         ADDRESS        PROGRAMMED   AGE
whereami-internal-http           gke-l7-rilb   10.10.15.205   True         6m5s
```

- Namespace Issued
```shell
kubectl appy -f gateway-cluster.yaml
```

Sample log output of the cert-manager-google-cas-issuer
```shell
# GoogleCASIssuer Logs
I0424 00:57:48.949666       1 request_controller.go:178] "msg"="Request has not been approved or denied. Ignoring." "CertificateRequest"={"name":"whereami-cluster-example-com-tls-1","namespace":"default"} "controller"="certificaterequest" "controllerGroup"="cert-manager.io" "controllerKind"="CertificateRequest" "logger"="Reconcile" "name"="whereami-cluster-example-com-tls-1" "namespace"="default" "reconcileID"="0865f4e5-0c09-4bb0-af74-f69d26444c4d"
I0424 00:57:49.002989       1 request_controller.go:229] "msg"="Initialised Ready condition" "CertificateRequest"={"name":"whereami-cluster-example-com-tls-1","namespace":"default"} "controller"="certificaterequest" "controllerGroup"="cert-manager.io" "controllerKind"="CertificateRequest" "logger"="Reconcile" "name"="whereami-cluster-example-com-tls-1" "namespace"="default" "reconcileID"="82bd89d5-c0f5-41ec-88f2-2b1a54445be1"
I0424 00:57:49.311666       1 request_controller.go:274] "msg"="Successfully finished the reconciliation." "CertificateRequest"={"name":"whereami-cluster-example-com-tls-1","namespace":"default"} "controller"="certificaterequest" "controllerGroup"="cert-manager.io" "controllerKind"="CertificateRequest" "logger"="Reconcile" "name"="whereami-cluster-example-com-tls-1" "namespace"="default" "reconcileID"="a6313167-0518-4840-9003-c8fdde9f47c9"
I0424 00:57:49.311925       1 recorder.go:104] "msg"="Succeeded signing the CertificateRequest" "logger"="events" "object"={"kind":"CertificateRequest","namespace":"default","name":"whereami-cluster-example-com-tls-1","uid":"07dc1667-3fe5-4118-a3ee-183b50208396","apiVersion":"cert-manager.io/v1","resourceVersion":"1745456269043711017"} "reason"="Issued" "type"="Normal"

# Output
NAME                             CLASS         ADDRESS        PROGRAMMED   AGE
whereami-internal-cluster-http   gke-l7-rilb   10.10.15.207   True         96s
```

## Optional
Deploy sample certificates to test our issuer

```shell
kubectl apply -f sample-cert-cluster.yaml
kubectl apply -f sample-cert.yaml
```