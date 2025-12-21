#!/bin/bash

# Test script to verify the viewer is working correctly

echo "🧪 Testing Palworld Save Viewer..."
echo ""

# Check if container is running
echo "1. Checking if container is running..."
if docker ps | grep -q palworld-save-viewer; then
    echo "   ✅ Container is running"
else
    echo "   ❌ Container is not running"
    echo "   Run: ./start.sh"
    exit 1
fi

echo ""

# Check if nginx is responding
echo "2. Testing nginx (frontend)..."
if curl -f -s http://localhost:5175/health > /dev/null 2>&1; then
    echo "   ✅ Nginx is responding"
else
    echo "   ❌ Nginx is not responding"
    exit 1
fi

echo ""

# Check if backend is responding
echo "3. Testing backend API..."
if curl -f -s http://localhost:5175/api/health > /dev/null 2>&1; then
    echo "   ✅ Backend API is responding"
else
    echo "   ❌ Backend API is not responding"
    exit 1
fi

echo ""

# Check save info
echo "4. Testing save info endpoint..."
RESPONSE=$(curl -s http://localhost:5175/api/info)
if echo "$RESPONSE" | grep -q "loaded"; then
    echo "   ✅ Save info endpoint working"
    echo ""
    echo "   Save Info:"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
else
    echo "   ❌ Save info endpoint failed"
    exit 1
fi

echo ""

# Check if save is loaded
echo "5. Checking if save is loaded..."
if echo "$RESPONSE" | grep -q '"loaded": true'; then
    echo "   ✅ Save file is loaded"
    
    # Get counts
    PLAYERS=$(curl -s http://localhost:5175/api/players | grep -o '"count":[0-9]*' | grep -o '[0-9]*')
    GUILDS=$(curl -s http://localhost:5175/api/guilds | grep -o '"count":[0-9]*' | grep -o '[0-9]*')
    PALS=$(curl -s http://localhost:5175/api/pals | grep -o '"count":[0-9]*' | grep -o '[0-9]*')
    
    echo "   📊 Statistics:"
    echo "      - Players: $PLAYERS"
    echo "      - Guilds: $GUILDS"
    echo "      - Pals: $PALS"
else
    echo "   ⚠️  Save file is not loaded"
    echo "   Check your volume mount in docker-compose.yml"
fi

echo ""
echo "✅ All tests passed!"
echo ""
echo "🌐 Access the viewer at: http://localhost:5175"
echo "📊 View logs with: ./logs.sh"
