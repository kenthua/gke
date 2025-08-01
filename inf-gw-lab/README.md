# GKE Inference Gateway

Set of scripts and Kubernetes configuration files to deploy Gemma models through vLLM on Google Kubernetes Engine (GKE). GKE Inference Gatewa is used to route traffic between models.

## Scripts
Intended to run in the order described:

- `setup.sh` - sets up the cluster and inference gateway prereqs

Choose 1 for 1b:

- `deploy-1b.sh` - deploys gemma 3 1b it resources

or

- `deploy-1b-ft.sh` - deploys gemma 3 1b resources and a lora adapter. You will need to add the lora adapter path to the script.

Continue from here:

- `deploy-4b.sh` - deploys gemma 3 4b it resources
- `deploy-ma.sh`- configures model armor for the gemama 3 1b it model, which assesses the prompt and responses for Responsible AI and safety filters.
- `deploy-ca.sh`- configures cloud armor for the gemma models, which requires a HTTP `user-id` header to access resources as a test.

## Test Queries and sample outputs

- Get the IP of the Gateway for queries to be used later

```bash
GW_IP=$(kubectl get gateway/vllm-xlb \
  -o jsonpath='{.status.addresses[0].value}')
GW_PORT=80

echo http://$GW_IP:$GW_PORT
```

### gemma 3 1b it

- Completions

```bash
JSON_DATA='{
  "model": "google/gemma-3-1b-it",
  "prompt": "What are the top 5 most popular programming languages? Please be brief.",
  "max_tokens": 200
}'

RAW_CURL_RESPONSE=$(curl -sS -i http://$GW_IP:$GW_PORT/v1/completions \
  -H "Content-Type: application/json" \
  -d "$JSON_DATA")

echo "---"
echo "$RAW_CURL_RESPONSE" | head -n 1
echo "$RAW_CURL_RESPONSE" | sed '1,/^\r*$/d' | jq .choices
```

- Chat Completions

```bash
JSON_DATA='{
  "model": "google/gemma-3-1b-it",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What are the top 5 most popular programming languages? Please be brief."}
  ],
  "temperature": 0.7
}'

RAW_CURL_RESPONSE=$(curl -sS -i http://$GW_IP:$GW_PORT/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "$JSON_DATA")

echo "---"
echo "$RAW_CURL_RESPONSE" | head -n 1
echo "$RAW_CURL_RESPONSE" | sed '1,/^\r*$/d' | jq
```

### gemma 3 4b it

```bash
# Data for the 4b model using chat completions
JSON_DATA='{
  "model": "google/gemma-3-4b-it",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What are the top 5 most popular programming languages? Please be brief."}
  ],
  "temperature": 0.7
}'

RAW_CURL_RESPONSE=$(curl -sS -i http://$GW_IP:$GW_PORT/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "$JSON_DATA")

echo "---"
echo "$RAW_CURL_RESPONSE" | head -n 1
echo "$RAW_CURL_RESPONSE" | sed '1,/^\r*$/d' | jq
```

### Model Armor

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

### Cloud Armor

```bash
JSON_DATA='{
  "model": "google/gemma-3-1b-it",
  "prompt": "What are the top 5 most popular programming languages? Please be brief.",
  "max_tokens": 200
}'

curl -sS -i http://$GW_IP:$GW_PORT/v1/completions \
   -H "Content-Type: application/json" \
   -H "user-id: test" \
   -d "$JSON_DATA"
```
