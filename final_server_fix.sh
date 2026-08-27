#!/bin/bash

CONTAINER_ID="5ecbf5b801b5"
API_FILE="/app/server.js"

echo "=== STEP 1: Completely rewrite server.js to proxy REAL data ==="
# Use Node.js to write a clean, working server
sudo docker exec -i "$CONTAINER_ID" node - << 'NODE_FINAL_FIX'
const fs = require('fs');

const filePath = '/app/server.js';
const newContent = `
import express from 'express'
import { createProxyMiddleware } from 'http-proxy-middleware'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const app = express()
const PORT = 3000

// 1. Proxy ALL /api requests directly to the Host API (port 3001)
// This bypasses the broken internal database entirely.
app.use('/api', createProxyMiddleware({
    target: 'http://host.docker.internal:3001',
    changeOrigin: true,
}));

// 2. Serve static frontend files (if any exist in dist)
app.use(express.static(path.join(__dirname, 'dist')));

app.listen(PORT, () => {
    console.log('✅ Frontend server running on port ' + PORT);
    console.log('✅ Real Docker data is proxied from host API on port 3001.');
});
`;

fs.writeFileSync(filePath, newContent);
console.log('✅ server.js successfully rewritten to proxy real data.');
NODE_FINAL_FIX

echo ""
echo "=== STEP 2: Ensure http-proxy-middleware is installed ==="
sudo docker exec "$CONTAINER_ID" sh -c "ls /app/node_modules/http-proxy-middleware > /dev/null 2>&1 && echo '✅ Already installed.' || (echo 'Installing...' && npm install http-proxy-middleware --save)"

echo ""
echo "=== STEP 3: Restart the frontend container ==="
sudo docker restart "$CONTAINER_ID"
sleep 8

echo ""
echo "=== STEP 4: Verify the server is running ==="
sudo docker exec "$CONTAINER_ID" sh -c "cat /proc/1/cmdline | tr '\0' ' '"
echo ""
echo ""

echo "=== STEP 5: Verify REAL data is flowing ==="
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
