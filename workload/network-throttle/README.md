### Network throttling

Utilizing [Traffic Shaping](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/#support-traffic-shaping), GKE 1.15+ with Network Policy and/or Interanode Visiblity enabled

* Get the IP of the pod / service for testing locally or remotely
  ```shell
  kubectl get po -o wide
  kubectl get svc 
  ```

* Exec into the client pod
  ```shell
  POD=$(kubectl get po -l app=iperf3-client -o name)
  kubectl exec -it $POD -- bash
  ```

* In the client pod run egress and ingress tests
  ```shell
  # for egress
  iperf3 -c $SERVER_IP
  # for ingress
  iperf3 -R -c $SERVER_IP
  ```
