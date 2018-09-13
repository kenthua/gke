### GKE with HTTPS Ingress, secret managed certificate for L7 LB
The app echo contains the certificate in the container image

```
kubectl apply -f gcp-secret-tls.yaml
kubectl apply -f app.yaml
```

## Bonus
If you want to create a global static IP and assign the DNS entry into your GCP Cloud DNS managed zone

* Create the static IP
```
gcloud compute addresses create echo --global
```
* What is the IP?
```
STATIC_IP=`gcloud compute addresses describe echo --global | grep address: | awk '{print $2}'`
```
* Add it to your managed Cloud DNS
```
DOMAIN_RECORD=your_dns.domain.com

cat <<EOF > dns.yaml 
kind: dns#resourceRecordSet
name: $DOMAIN_RECORD
rrdatas:
- $STATIC_IP
ttl: 300
type: A
EOF
```
```
gcloud dns record-sets import dns.yaml --zone gcp-testing-pitchdarkice-com
```
* Modify your ingress annotation to reference the static IP, add the following annotation to your ingress object
```
kubernetes.io/ingress.global-static-ip-name: echo
```

