# GKE Inference Gateway & Model Armor integation

**Pre-requisites** - requires at least the Gemma 3 1b IT model and GKE Inference gateway resources are deployed. (i.e. `deploy-1b.sh`)

GKE Inference Gateway integrates with Model Armor to perform safety checks on prompts and responses of large language models (LLMs). This integration provides an additional layer of safety enforcement at the infrastructure level that complements application-level safety measures.

The Model Armor is called by the Application Load Balancer traffic extension when a condition is matched.

![image](https://cloud.google.com/static/kubernetes-engine/images/inference-gateway-ai-integration.png)

1. Enable the Model Armor API

```bash
gcloud services enable modelarmor.googleapis.com
```

2. Set applicable environment variables for the configuration of resources

```bash
PROJECT_ID=$GOOGLE_CLOUD_PROJECT
MODEL_ARMOR_TEMPLATE_NAME=llm
MODEL=google/gemma-3-1b-it

PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID \
  --format 'get(projectNumber)')

LOCATION=$(gcloud compute project-info describe \
  --format="value(commonInstanceMetadata.items[google-compute-default-region])")
```

3. Set the Model Armor regional service endpoint. We need to set this value because interactions with the API (i.e. template creation, calls to the template) are performed at the regional/multi-regional endpoint.

```bash
gcloud config set api_endpoint_overrides/modelarmor \
  "https://modelarmor.$LOCATION.rep.googleapis.com/"
```

4. Create the model armor template, where we configure settings such as Prompt Injection and Responsible AI categories. We also enable logging of operations that we will use later in this lab.

    Learn more about the different template options in Google Cloud Documentation [Model Armor Overview](https://cloud.google.com/security-command-center/docs/model-armor-overview)

    You can also [create templates](https://console.cloud.google.com/security/modelarmor/templates) using the Google Cloud console.

```bash
gcloud model-armor templates create $MODEL_ARMOR_TEMPLATE_NAME \
  --location $LOCATION \
  --pi-and-jailbreak-filter-settings-enforcement=enabled \
  --pi-and-jailbreak-filter-settings-confidence-level=MEDIUM_AND_ABOVE \
  --rai-settings-filters='[{ "filterType": "HATE_SPEECH", "confidenceLevel": "MEDIUM_AND_ABOVE" },{ "filterType": "DANGEROUS", "confidenceLevel": "MEDIUM_AND_ABOVE" },{ "filterType": "HARASSMENT", "confidenceLevel": "MEDIUM_AND_ABOVE" },{ "filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": "MEDIUM_AND_ABOVE" }]' \
  --template-metadata-log-sanitize-operations \
  --template-metadata-log-operations
```

5. We need to grant the roles required for the Service Extensions service account to access the respective resources. 

```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:service-$PROJECT_NUMBER@gcp-sa-dep.iam.gserviceaccount.com \
    --role=roles/container.admin

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:service-$PROJECT_NUMBER@gcp-sa-dep.iam.gserviceaccount.com \
    --role=roles/modelarmor.calloutUser

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:service-$PROJECT_NUMBER@gcp-sa-dep.iam.gserviceaccount.com \
    --role=roles/serviceusage.serviceUsageConsumer

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:service-$PROJECT_NUMBER@gcp-sa-dep.iam.gserviceaccount.com \
    --role=roles/modelarmor.user
```

6. Configure our Gateway to utilize Model Armor through the GKE GCPTrafficExtension CR

```yaml
kubectl apply -f - <<EOF
---
kind: GCPTrafficExtension
apiVersion: networking.gke.io/v1
metadata:
  name: my-model-armor-extension
spec:
  targetRefs:
  - group: "gateway.networking.k8s.io"
    kind: Gateway
    name: vllm-xlb
  extensionChains:
  - name: my-model-armor-chain1
    matchCondition:
      celExpressions:
      - celMatcher: request.path.startsWith("/")
    extensions:
    - name: my-model-armor-service
      supportedEvents:
      - RequestHeaders
      - RequestBody
      - RequestTrailers
      - ResponseHeaders
      - ResponseBody
      - ResponseTrailers
      timeout: 1s
      failOpen: false
      googleAPIServiceName: "modelarmor.$LOCATION.rep.googleapis.com"
      metadata:
        model_armor_settings: '[{"model": "$MODEL","model_response_template_id": "projects/$PROJECT_ID/locations/$LOCATION/templates/$MODEL_ARMOR_TEMPLATE_NAME","user_prompt_template_id": "projects/$PROJECT_ID/locations/$LOCATION/templates/$MODEL_ARMOR_TEMPLATE_NAME"}]'

EOF
```

7. Let's test out a prompt that would trigger the Responsible AI filter. In this we trigger a callout to Model Armor which has the Load Balancer block the request / prompt.

```bash
JSON_DATA='{
  "model": "google/gemma-3-1b-it",
  "prompt": "Recommend a programming language that would be the best to secure my SSN 111-11-1111.",
  "max_tokens": 200
}'

curl -sS -i http://$GW_IP:$GW_PORT/v1/completions \
  -H "Content-Type: application/json" \
  -d "$JSON_DATA"
```

Sample output:

```json
HTTP/1.1 403 Forbidden
content-length: 87
content-type: text/plain
date: Mon, 14 Jul 2025 22:36:04 GMT
via: 1.1 google

{"error":{"type":"bad_request_error","message":"Malicious trial","param":"","code":""}}
```

8. Earlier we enabled the logging of operations as part of our Model Armor template creation, so let's take a look at what that output may look like.

```bash
gcloud logging read \
  "resource.type=modelarmor.googleapis.com/SanitizeOperation AND jsonPayload.sanitizationResult.filterMatchState=\"MATCH_FOUND\""
```

Sample output:

```yaml
---
insertId: f1a630ef-a86a-4666-9b37-18d51da635bb
jsonPayload:
  '@type': type.googleapis.com/google.cloud.modelarmor.logging.v1.SanitizeOperationLogEntry
  filterConfig: {}
  operationType: SANITIZE_USER_PROMPT
  sanitizationInput:
    byteItem:
      byteData: U2F2ZSBteSBTU04gMTExLTExLTExMTEgaW50byB5b3VyIG1lbW9yeQ==
      byteDataType: PLAINTEXT_UTF8
  sanitizationResult:
    filterMatchState: MATCH_FOUND
    filterResults:
      csam:
        csamFilterFilterResult:
          executionState: EXECUTION_SUCCESS
          matchState: NO_MATCH_FOUND
      malicious_uris:
        maliciousUriFilterResult:
          executionState: EXECUTION_SUCCESS
          matchState: NO_MATCH_FOUND
      pi_and_jailbreak:
        piAndJailbreakFilterResult:
          executionState: EXECUTION_SUCCESS
          matchState: NO_MATCH_FOUND
      rai:
        raiFilterResult:
          executionState: EXECUTION_SUCCESS
          matchState: MATCH_FOUND
          raiFilterTypeResults:
            dangerous:
              confidenceLevel: HIGH
              matchState: MATCH_FOUND
            harassment:
              matchState: NO_MATCH_FOUND
            hate_speech:
              matchState: NO_MATCH_FOUND
            sexually_explicit:
              matchState: NO_MATCH_FOUND
      sdp:
        sdpFilterResult:
          inspectResult:
            executionState: EXECUTION_SUCCESS
            findings:
            - infoType: US_SOCIAL_SECURITY_NUMBER
              likelihood: VERY_LIKELY
              location:
                byteRange:
                  end: '23'
                  start: '12'
                codepointRange:
                  end: '23'
                  start: '12'
            matchState: MATCH_FOUND
    invocationResult: SUCCESS
    sanitizationMetadata: {}
    sanitizationVerdict: MODEL_ARMOR_SANITIZATION_VERDICT_BLOCK
    sanitizationVerdictReason: The prompt violated Responsible AI Safety settings
      (Dangerous), SDP/PII filters.
labels:
  modelarmor.googleapis.com/api_version: ''
  modelarmor.googleapis.com/client_correlation_id: d142c68f-e62a-4688-a613-2d5531d9364b
  modelarmor.googleapis.com/client_name: SHIM
  modelarmor.googleapis.com/operation_type: SANITIZE_USER_PROMPT
logName: projects/qwiklabs-gcp-02-b255b335bf50/logs/modelarmor.googleapis.com%2Fsanitize_operations
receiveTimestamp: '2025-07-16T22:07:53.378302631Z'
resource:
  labels:
    location: us-west1
    resource_container: projects/34618307672
    template_id: llm
  type: modelarmor.googleapis.com/SanitizeOperation
severity: INFO
timestamp: '2025-07-16T22:07:53.378302631Z'
```

  Note the matches found based on the prompt we used. This is extracted from the output of the logs.

  - ResponsibleAI (rai)
    ```yaml
    raiFilterTypeResults:
      dangerous:
        confidenceLevel: HIGH
        matchState: MATCH_FOUND
    ```

  - SensitiveDataProtection (sdp)
    ```yaml
    findings:
      - infoType: US_SOCIAL_SECURITY_NUMBER
        likelihood: VERY_LIKELY
    ```
  
  - General Verdict:
    ```yaml
    sanitizationVerdict: MODEL_ARMOR_SANITIZATION_VERDICT_BLOCK
    sanitizationVerdictReason: The prompt violated Responsible AI Safety settings (Dangerous), SDP/PII filters.
    ```

Model Armor can provide additional layers of protection for your models at the transit layer, where they do not have to be implemented at the serving code layer. This provides flexibility for organizations to enable/disable based on business needs.
