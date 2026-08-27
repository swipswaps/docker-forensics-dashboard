#!/bin/bash

echo "=== STEP 1: Recreating Frontend Dashboard Container ==="
# Recreate the frontend container using the known image.
# It binds ONLY to port 3000 (frontend), because port 3001 is now handled by our host API proxy.
sudo docker run -d \
  --name notes-forensic-dashboard-1 \
  -p 3000:3000 \
  notes-forensic-dashboard:latest \
  npm run dev

echo ""
echo "=== STEP 2: Wait for container to boot ==="
sleep 8

echo ""
echo "=== STEP 3: Verify Frontend is Running ==="
if sudo lsof -i :3000 > /dev/null 2>&1; then
    echo "✅ Frontend is running on http://localhost:3000"
    echo "   You can now open Firefox and refresh the dashboard."
else
    echo "❌ Frontend failed to start. Checking logs..."
    sudo docker logs notes-forensic-dashboard-1 --tail 30
fi

echo ""
echo "=== STEP 4: Verify Backend API is Still Running ==="
if sudo lsof -i :3001 > /dev/null 2>&1; then
    echo "✅ Backend API is running on port 3001."
    echo "   The real Docker data is flowing."
else
    echo "❌ Backend API is down. Restarting systemd service..."
    sudo systemctl restart forensic-host-api
    sleep 3
fi
