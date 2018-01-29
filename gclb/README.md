# GCLB Examples

[Service annotations](https://github.com/kubernetes/ingress-gce/blob/master/pkg/annotations/service.go#L31) and [Backend HTTPS](https://github.com/kubernetes/ingress-gce/blob/master/README.md)
[Ingress annotations](https://github.com/kubernetes/ingress-gce/blob/master/docs/annotations.md)

### Notes
* Note the annotation `service.alpha.kubernetes.io/app-protocols` in the service manifest.  It is required for HTTPS backend support.  i.e. End to End SSL for the GCLB HTTPS L7.  The HTTPS L7 LB will terminate the SSL end point and the backend will initiate another SSL session exposed by the service/pod.