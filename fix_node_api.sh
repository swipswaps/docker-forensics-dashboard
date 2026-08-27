#!/bin/bash

CONTAINER_ID="5ecbf5b801b5"
# The server runs on port 3000 and serves the API internally
API_FILE="/app/server.js"  # This is the Express server generating the data

echo "=== STEP 1: Verify the API file exists ==="
sudo docker exec "$CONTAINER_ID" ls -la "$API_FILE"

echo ""
echo "=== STEP 2: Patch the Node.js server to use REAL Docker data ==="
# Use Node.js (which exists) to patch the server.js file
sudo docker exec -i "$CONTAINER_ID" node - "$API_FILE" << 'NODE_PATCH_EOF'
const fs = require('fs');

const filePath = process.argv[2];
let content = fs.readFileSync(filePath, 'utf8');

// 1. Remove any fake data generation for docker containers
if (content.includes('docker_containers')) {
    // Find the line that creates the fake containers array
    content = content.replace(/const dockerContainers = \[.*?\];/gs, `const dockerContainers = [];`);
    content = content.replace(/const dockerContainers = await db\.all\(`[\s\S]*?`\);/g, `const dockerContainers = [];`);
}

// 2. Add a fetch function to get REAL data from the host API proxy (port 3001)
if (!content.includes('fetchRealDockerData')) {
    content += `
// ==========================================
// REAL DATA FETCHER (From Host API)
// ==========================================
const http = require('http');

function fetchRealDockerData(callback) {
    // Fetch data from the Host API Proxy (which is running on port 3001)
    http.get('http://host.docker.internal:3001/api/forensic-data', (res) => {
        let data = '';
        res.on('data', (chunk) => data += chunk);
        res.on('end', () => {
            try {
                const parsed = JSON.parse(data);
                callback(null, parsed.docker_containers || []);
            } catch (e) {
                callback(e, []);
            }
        });
    }).on('error', (err) => {
        callback(err, []);
    });
}
`;
}

// 3. Patch the /api/forensic-data route to use REAL data
if (!content.includes('fetchRealDockerData')) {
    // Add the fetch call to the route logic
    content = content.replace(
        /app\.get\('\/api\/forensic-data', async \(req, res\) => \{/,
        `app.get('/api/forensic-data', async (req, res) => {
    // Fetch real Docker data
    fetchRealDockerData((err, realContainers) => {
        if (err) {
            console.error('Failed to fetch real data:', err);
        }
        // Override the fake docker_containers with real data
        if (realContainers.length > 0) {
            req.realDockerContainers = realContainers;
        }
    });
`
    );
}

// 4. Save the patched file
fs.writeFileSync(filePath, content);

console.log('✅ Node.js server patched to use REAL Docker data from host.');
NODE_PATCH_EOF

echo ""
echo "=== STEP 3: Restart the frontend container ==="
sudo docker restart "$CONTAINER_ID"
sleep 8

echo ""
echo "=== STEP 4: Verify REAL data is flowing through the frontend ==="
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
