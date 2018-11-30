#!/bin/sh
./vault status
./vault token lookup
./vault kv get secret/my-secret
./vault kv get -format=yaml secret/my-secret > /work-dir/output.yaml
