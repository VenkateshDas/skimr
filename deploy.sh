#!/bin/bash

# Ensure the script is executable with: chmod +x deploy.sh

# Build and run the Docker container in detached mode for production
docker-compose up -d --build

echo "YouTube Analyzer deployed and running at http://localhost:8501" 