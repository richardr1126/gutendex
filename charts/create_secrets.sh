#!/bin/bash

# Script to create the Kubernetes secret for Gutendex
# This script creates the secret from environment variables defined in .env file

set -e

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: .env file not found at $ENV_FILE"
  echo "Copy .env.example to .env and fill it in:"
  echo "SECRET_KEY=        # openssl rand -hex 32"
  echo "API_KEYS=          # openssl rand -hex 32; comma-separate several to rotate"
  exit 1
fi

# Load environment variables from .env file
echo "Loading environment variables from $ENV_FILE"
set -a  # automatically export all variables
source "$ENV_FILE"
set +a  # stop automatically exporting

# Validate that required variables are set
required_vars=("SECRET_KEY" "API_KEYS")
for var in "${required_vars[@]}"; do
  if [ -z "${!var}" ]; then
    echo "Error: $var is not set in .env file"
    exit 1
  fi
done

# Create or update in place, so a rerun after rotating API_KEYS does not leave
# a window with no secret. Pods read it at start: after a change, run
# kubectl rollout restart deployment/gutendex-main
# The database password is not here: CloudNativePG generates it in the
# gutendex-db-app secret.
echo "Creating gutendex-secrets..."
kubectl create secret generic gutendex-secrets \
  --from-literal=SECRET_KEY="${SECRET_KEY}" \
  --from-literal=API_KEYS="${API_KEYS}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secrets created successfully!"
