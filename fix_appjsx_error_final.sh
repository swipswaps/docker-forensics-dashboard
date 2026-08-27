#!/bin/bash

CONTAINER_ID="5ecbf5b801b5"
APP_JSX="/app/src/App.jsx"

echo "=== RAW TELEMETRY: Confirm container is running ==="
if ! sudo docker ps --format "{{.Names}}" | grep -q "$CONTAINER_ID"; then
    echo "❌ CONTAINER NOT RUNNING. Check: docker ps"
    exit 1
fi
echo "✅ Container running."

echo ""
echo "=== RAW TELEMETRY: Read current App.jsx line count and error area ==="
sudo docker exec "$CONTAINER_ID" wc -l "$APP_JSX"
sudo docker exec "$CONTAINER_ID" sed -n '265,275p' "$APP_JSX"

echo ""
echo "=== ACTION: Use Node.js to surgically remove the broken block ==="
sudo docker exec -i "$CONTAINER_ID" node - << 'NODE_REPAIR_JSX'
const fs = require('fs');
const filePath = '/app/src/App.jsx';
const content = fs.readFileSync(filePath, 'utf8');

// 1. Find the broken stray tags
const brokenStart = content.indexOf('      )}\n      \n                </tbody>');
const brokenEnd = content.indexOf('          </div>\n        </div>\n      )}\n\n      {selectedView === \'metrics\' && (');

if (brokenStart > -1 && brokenEnd > -1) {
    // Remove the broken block (lines 267-272)
    const cleanContent = content.substring(0, brokenStart) + content.substring(brokenEnd);
    
    // Rewrite the file
    fs.writeFileSync(filePath, cleanContent);
    console.log('✅ Broken JSX block removed successfully.');
} else {
    console.log('ℹ️ Exact broken block not found. Attempting line-based repair...');
    
    // Fallback: Remove lines 267-272 (0-indexed: 266-271)
    const lines = content.split('\n');
    const newLines = lines.filter((_, index) => index < 266 || index > 271);
    fs.writeFileSync(filePath, newLines.join('\n'));
    console.log('✅ Lines 267-272 removed.');
}

// Ensure the file ends correctly
const finalContent = fs.readFileSync(filePath, 'utf8');
if (!finalContent.trim().endsWith('export default App')) {
    finalContent += '\n    </div>\n  )\n}\n\nexport default App\n';
    fs.writeFileSync(filePath, finalContent);
    console.log('✅ Final closing structure added.');
}
NODE_REPAIR_JSX

echo ""
echo "=== RAW TELEMETRY: Verify JSX compiles correctly ==="
sudo docker exec "$CONTAINER_ID" sh -c "cd /app && npx vite build 2>&1 | head -n 30"

echo ""
echo "=== RAW TELEMETRY: Restart and Verify API ==="
sudo docker restart "$CONTAINER_ID"
sleep 8

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
