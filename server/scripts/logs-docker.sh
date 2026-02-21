#!/bin/bash
set -e

# Script to view Docker container logs

if [ $# -ne 1 ]; then
  echo "Usage: $0 <environment>"
  echo "Environments: development, staging, production"
  exit 1
fi

ENV=$1

# Validate environment
if [[ ! "$ENV" =~ ^(development|staging|production)$ ]]; then
  echo "Invalid environment. Must be one of: development, staging, production"
  exit 1
fi

# Load PROJECT_NAME from env file
ENV_FILE=".env.$ENV"
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

# Normalize project name for Docker
DOCKER_IMAGE_NAME=$(echo "${PROJECT_NAME:-fastapi-app}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//' | sed 's/-$//')
CONTAINER_NAME="$DOCKER_IMAGE_NAME-$ENV"

echo "Viewing logs for $ENV environment container"

# Check if container exists
if [ ! "$(docker ps -a -q -f name=$CONTAINER_NAME)" ]; then
  echo "Container $CONTAINER_NAME does not exist. Please run it first with:"
  echo "make docker-run-env ENV=$ENV"
  exit 1
fi

# Get container status
STATUS=$(docker inspect --format='{{.State.Status}}' $CONTAINER_NAME 2>/dev/null)

if [ "$STATUS" != "running" ]; then
  echo "Container $CONTAINER_NAME is not running (status: $STATUS)"
  echo "To start it, run: docker start $CONTAINER_NAME"
  exit 1
fi

# Display logs with follow option
echo "Following logs from $CONTAINER_NAME (Ctrl+C to exit)"
docker logs -f $CONTAINER_NAME 