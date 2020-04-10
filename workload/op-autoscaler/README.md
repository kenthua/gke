Testing with 2 core nodes with cluster autoscaler enabled.  Tweaking will need
to be done to the configmap given the ratio provided.  Based on the defined
`coresPerReplica: 20` for each 20 cores in the cluster, there will be 1
overprovisioning pod replica.
