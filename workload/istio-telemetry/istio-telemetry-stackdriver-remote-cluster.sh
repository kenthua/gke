#!/bin/bash
# For istio 1.4.x
BASE=istio-telemetry-stackdriver
INPUT=$BASE.yaml
OUTPUT=$BASE-aws.yaml
PROJECT_ID=<gcp-project>
CLUSTER_NAME=<cluster>
LOCATION="<valid gcp region>"
sed "0,/  params:/s/  params:/  params:\n    project_id: \"$PROJECT_ID\"/" $INPUT > $OUTPUT
sed -i "s/project_id: '\"\"'/project_id: '\"$PROJECT_ID\"'/g" $OUTPUT
sed -i "s/cluster_name: '\"\"'/cluster_name: '\"$CLUSTER_NAME\"'/g" $OUTPUT
sed -i "s/location: '\"\"'/location: '\"$LOCATION\"'/g" $OUTPUT
