# GKE Inference Gateway

Set of scripts and Kubernetes configuration files to deploy Gemma models through vLLM on Google Kubernetes Engine (GKE). GKE Inference Gatewa is used to route traffic between models.

## Scripts
Intended to run in the order described:

- `setup.sh` - sets up the cluster and inference gateway prereqs
- `deploy-1b.sh` - deploys gemma 3 1b it resources
- `deploy-4b.sh` - deploys gemma 3 4b it resources
- `deploy-ma.sh`- configures model armor for the gemama 3 1b it model, which assesses the prompt and responses for Responsible AI and safety filters.
- `deploy-ca.sh`- configures cloud armor for the gemma models, which requires a HTTP `user-id` header to access resources as a test.
