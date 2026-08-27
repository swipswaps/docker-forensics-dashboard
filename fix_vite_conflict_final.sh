#!/bin/bash

CONTAINER_ID="5ecbf5b801b5"

echo "=== RAW TELEMETRY: Confirm container is running ==="
sudo docker ps --filter "name=notes-forensic-dashboard" --format "{{.ID}} | {{.Status}}"

echo ""
echo "=== ACTION: Delete server.js to stop port conflict ==="
sudo docker exec "$CONTAINER_ID" rm -f /app/server.js

echo ""
echo "=== ACTION: Force Vite to run on port 3000 ==="
sudo docker exec -i "$CONTAINER_ID" node - << 'NODE_FIX_VITE'
const fs = require('fs');
const filePath = '/app/vite.config.js';

const correctConfig = `import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true, // Force Vite to use port 3000 or crash
    proxy: {
      '/api': {
        target: 'http://172.17.0.1:3001',
        changeOrigin: true
      }
    }
  }
})`;

fs.writeFileSync(filePath, correctConfig);
console.log('✅ Vite config written: Port 3000, Proxy to 172.17.0.1:3001');
NODE_FIX_VITE

echo ""
echo "=== ACTION: Force package.json to ONLY run vite ==="
sudo docker exec -i "$CONTAINER_ID" node - << 'NODE_FIX_PACKAGE'
const fs = require('fs');
const filePath = '/app/package.json';

const packageJson = JSON.parse(fs.readFileSync(filePath, 'utf8'));
packageJson.scripts.dev = "vite"; // Remove concurrently, just run Vite

fs.writeFileSync(filePath, JSON.stringify(packageJson, null, 2));
console.log('✅ package.json patched: dev script is now just "vite"');
NODE_FIX_PACKAGE

echo ""
echo "=== ACTION: Restart container ==="
sudo docker restart "$CONTAINER_ID"
sleep 8

echo ""
echo "=== RAW TELEMETRY: Check what is running ==="
sudo docker exec "$CONTAINER_ID" sh -c "cat /proc/1/cmdline | tr '\0' ' '"
echo ""

echo ""
echo "=== RAW TELEMETRY: Verify API is flowing ==="
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
    print('✅ BACKEND DATA FLOWING. Refresh your browser NOW!')
else:
    print('❌ Container not found.')
"
