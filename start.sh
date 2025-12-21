#!/bin/bash

# Build and start the Palworld Save Viewer
echo "🔨 Building Palworld Save Viewer..."
docker compose build

echo "🚀 Starting Palworld Save Viewer..."
docker compose up -d

echo "✅ Viewer started!"
echo "📍 Access at: http://localhost:5175"
echo "📊 Logs: docker compose logs -f"
