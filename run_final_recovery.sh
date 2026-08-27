#!/bin/bash

CONTAINER_ID="5ecbf5b801b5"

echo "=== STEP 1: Copy the COMPLETE working frontend into container ==="
# Use 'App_with_dirs_final.jsx' which has ALL features (from your telemetry)
sudo docker cp /home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/notes/src/App_with_dirs_final.jsx "$CONTAINER_ID":/app/src/App.jsx

echo ""
echo "=== STEP 2: Restart container to load full frontend ==="
sudo docker restart "$CONTAINER_ID"
sleep 8

echo ""
echo "=== STEP 3: Verify the container is running ==="
sudo docker ps --filter "id=$CONTAINER_ID" --format "{{.Names}} | {{.Status}}"

echo ""
echo "=== STEP 4: Verify the API returns ALL expected data fields ==="
curl -s http://localhost:3001/api/forensic-data | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('✅ API is live.')
print(f'  - Docker Containers: {len(data.get(\"docker_containers\", []))}')
print(f'  - Directories: {len(data.get(\"detected_directories\", []))}')
print(f'  - System Load: {len(data.get(\"system_load\", []))}')
print(f'  - High CPU Processes: {len(data.get(\"high_cpu_processes\", []))}')

# Verify real_info mounts are present
containers = data.get('docker_containers', [])
for c in containers:
    if c.get('name') == 'repo-setup-redis':
        mounts = c.get('real_info', {}).get('mounts', [])
        if len(mounts) > 0:
            print('  - Real Mounts for repo-setup-redis:')
            for m in mounts:
                print(f'      {m.get(\"Source\")} -> {m.get(\"Destination\")}')
        else:
            print('  - ⚠️ Mounts for repo-setup-redis are empty (API needs to pass real_info properly).')
        break
"

echo ""
echo "=== STEP 5: Fix the API (if mounts are missing) ==="
# The 'App_with_dirs_final.jsx' expects 'real_info' to be present.
# Check if host_api_proxy.py is running and serving this.
sudo systemctl status forensic-host-api --no-pager | head -n 5

echo ""
echo "=== DONE. Refresh the browser NOW. ==="
echo "Access: http://localhost:3000"
