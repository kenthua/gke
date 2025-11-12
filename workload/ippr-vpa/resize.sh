POD=$1

kubectl patch pod $POD --subresource resize --patch \
  '{"spec":{"containers":[{"name":"whereami", "resources":{"requests":{"cpu":"200m"}, "limits":{"cpu":"200m"}}}]}}'

kubectl patch pod $POD --subresource resize --patch \
  '{"spec":{"containers":[{"name":"whereami", "resources":{"requests":{"memory":"500Mi"}, "limits":{"memory":"500Mi"}}}]}}'
