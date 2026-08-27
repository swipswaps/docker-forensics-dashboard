#!/bin/bash

SERVICE_NAME="forensic-host-api"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=== STEP 1: Kill the manual nohup process holding port 3001 ==="
# Kill the manual process (started with nohup earlier)
sudo pkill -f "host_api_proxy.py" 2>/dev/null
# Kill anything else on port 3001
sudo lsof -ti:3001 | xargs -r sudo kill -9 2>/dev/null
sleep 2

echo "✅ Old manual process killed. Port 3001 should be free."

echo ""
echo "=== STEP 2: Restart the systemd service ==="
sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE_NAME"

echo ""
echo "=== STEP 3: Verify the service is stable ==="
sleep 5
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Service '$SERVICE_NAME' is ACTIVE and stable."
    echo "   It will now automatically start on boot."
else
    echo "❌ Service still failing. Checking status..."
    sudo systemctl status "$SERVICE_NAME" --no-pager | tail -n 15
fi

echo ""
echo "=== STEP 4: Verify REAL Data is Flowing ==="
curl -s http://localhost:3001/api/forensic-data | python3 -c "
import sys, json
data = json.load(sys.stdin)
containers = data.get('docker_containers', [])
target = next((c for c in containers if c.get('name') == 'repo-setup-redis'), None)
if target:
    mounts = target.get('real_info', {}).get('mounts', [])
    print(f'Container: repo-setup-redis')
    print(f'REAL Mounts found: {len(mounts)}')
    for m in mounts:
        print(f'  - {m.get(\"Source\")} -> {m.get(\"Destination\")}')
    print('')
    print('✅ SUCCESS! Refresh your dashboard NOW!' if len(mounts) > 0 else '⚠️ Mounts empty.')
else:
    print('❌ Container not found in API response.')
"
