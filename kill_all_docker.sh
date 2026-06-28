#!/bin/bash

# Fetch a list of all running container IDs
RUNNING_CONTAINERS=$(docker ps -q)

if [ -z "$RUNNING_CONTAINERS" ]; then
    echo "ℹ️ No running Docker containers found to kill."
else
    echo "🛑 Force-killing all active Docker containers..."
    # Sends an immediate SIGKILL signal to shut down all processes instantly
    docker kill $RUNNING_CONTAINERS
    echo "✅ All containers killed successfully."
fi

# Optional: Clean up and remove the stopped container bodies from system memory
echo "🧹 Purging stopped container instances from the layout registry..."
docker rm $(docker ps -a -q) 2>/dev/null || echo "✨ Registry is already completely clear."
