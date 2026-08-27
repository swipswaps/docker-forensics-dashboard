#!/bin/bash

CONTAINER_ID="5ecbf5b801b5"
VITE_CONFIG="/app/vite.config.js"

echo "=== STEP 1: Check current vite.config.js ==="
sudo docker exec "$CONTAINER_ID" cat "$VITE_CONFIG"

echo ""
echo "=== STEP 2: Patch vite.config.js to proxy /api to host ==="
# Use Node.js to rewrite the Vite config
sudo docker exec -i "$CONTAINER_ID" node - << 'NODE_VITE_FIX'
const fs = require('fs');

const filePath = '/app/vite.config.js';
const currentContent = fs.readFileSync(filePath, 'utf8');

// If it doesn't have the proxy, add it
if (!currentContent.includes('proxy')) {
    const newContent = `
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://host.docker.internal:3001',
        changeOrigin: true,
      },
    },
  },
})
`;
    fs.writeFileSync(filePath, newContent);
    console.log('✅ Vite config patched with API proxy.');
} else {
    console.log('✅ Vite config already has proxy. Updating target...');
    const newContent = currentContent.replace(
        /target: '.*?'/,
        "target: 'http://host.docker.internal:3001'"
    );
    fs.writeFileSync(filePath, newContent);
    console.log('✅ Vite config updated.');
}
NODE_VITE_FIX

echo ""
echo "=== STEP 3: Restart the frontend container ==="
sudo docker restart "$CONTAINER_ID"
sleep 8

echo ""
echo "=== STEP 4: Verify REAL data is flowing through Vite ==="
curl -s http://localhost:3000/api/forensic-data | python3 -c "
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
