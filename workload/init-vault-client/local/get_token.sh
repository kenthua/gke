source vault.env
export VAULT_TOKEN=$(gsutil cat gs://${GCS_BUCKET_NAME}/root-token.enc | \
  base64 -d | \
  gcloud kms decrypt \
    --project ${PROJECT_ID} \
    --location global \
    --keyring vault \
    --key vault-init \
    --ciphertext-file - \
    --plaintext-file - 
)
