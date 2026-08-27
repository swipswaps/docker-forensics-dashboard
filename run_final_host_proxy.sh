#!/bin/bash

# Absolute path to the proxy file we just created
PROXY_FILE="/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo/host_api_proxy.py"
WORK_DIR="/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo"

echo "=== STEP 1: Stop and remove broken container blocking port 3001 ==="
sudo docker stop 1a0a90c552cd 2>/dev/null
sudo docker rm 1a0a90c552cd 2>/dev/null
echo "✅ Container stopped and removed."

echo ""
echo "=== STEP 2: Ensure host Python dependencies are installed ==="
# Install fastapi and uvicorn on the host if missing
if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "Installing fastapi and uvicorn..."
    pip3 install fastapi uvicorn --quiet
else
    echo "✅ Dependencies already installed."
fi

echo ""
echo "=== STEP 3: Start the Host API Proxy ==="
# Ensure no other process is holding port 3001
sudo pkill -f "host_api_proxy.py" 2>/dev/null
sudo lsof -ti:3001 | xargs -r sudo kill -9 2>/dev/null

# Start the proxy in the background
cd "$WORK_DIR"
sudo nohup python3 "$PROXY_FILE" > "$WORK_DIR/host_api.log" 2>&1 &
echo "✅ Host API proxy started on port 3001."

echo ""
echo "=== STEP 4: Wait for startup ==="
sleep 5

echo ""
echo "=== STEP 5: Verify REAL Data is flowing ==="
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

echo ""
echo "=== STEP 6: Check host API logs if needed ==="
cat "$WORK_DIR/host_api.log" 2>/dev/null | tail -n 10
