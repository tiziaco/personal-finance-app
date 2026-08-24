#!/bin/bash
set -e

# Script to stop and remove Docker containers

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

echo "Stopping container for $ENV environment"

# Check if container exists
if [ ! "$(docker ps -a -q -f name=$CONTAINER_NAME)" ]; then
    echo "Container $CONTAINER_NAME does not exist. Nothing to do."
    exit 0
fi

# Stop and remove container
echo "Stopping container $CONTAINER_NAME..."
docker stop $CONTAINER_NAME >/dev/null 2>&1 || echo "Container was not running"

echo "Removing container $CONTAINER_NAME..."
docker rm $CONTAINER_NAME >/dev/null 2>&1

echo "Container $CONTAINER_NAME stopped and removed successfully"
