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
echo "=== RAW TELEMETRY: Reading current App.jsx to find broken structure ==="
sudo docker exec "$CONTAINER_ID" wc -l "$APP_JSX"

echo ""
echo "=== ACTION: Use Node.js to repair the JSX structure ==="
sudo docker exec -i "$CONTAINER_ID" node - << 'NODE_REPAIR_ACTION'
const fs = require('fs');

const filePath = '/app/src/App.jsx';
const content = fs.readFileSync(filePath, 'utf8');

// 1. Find the broken appended section (the duplicate docker block)
// We look for the first occurrence of "Container Forensics" that appears AFTER the metrics section
const metricsIndex = content.indexOf('{selectedView === \'metrics\' && (');
const brokenIndex = content.indexOf('Container Forensics (Real Data)');

if (brokenIndex > -1 && metricsIndex > -1 && brokenIndex > metricsIndex) {
    // Remove everything from the brokenIndex to the end of the file
    content = content.substring(0, metricsIndex);
    
    // 2. Ensure the metrics section is properly closed
    // We need to append the missing closing braces and the App export
    const closingStructure = `
      {selectedView === 'metrics' && (
        <div className="grid full-width">
          <div className="card">
            <h2>System Metrics Over Time</h2>
            <div className="metrics-grid">
              <div className="metric-item">
                <h3>CPU Load Trend</h3>
                <ResponsiveContainer width="100%" height={150}>
                  <LineChart data={data.system_load}>
                    <XAxis dataKey="timestamp" />
                    <YAxis domain={[0, 2]} />
                    <Tooltip />
                    <Line type="monotone" dataKey="load_1m" stroke="#8884d8" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="metric-item">
                <h3>Memory Usage</h3>
                <ResponsiveContainer width="100%" height={150}>
                  <BarChart data={data.memory_usage}>
                    <XAxis dataKey="timestamp" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="used_mb" fill="#82ca9d" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
`;

    fs.writeFileSync(filePath, content + closingStructure);
    console.log('✅ App.jsx surgically repaired. Broken duplicate section removed.');
} else {
    // If the broken section doesn't exist, we just need to fix the closing structure
    console.log('ℹ️ Broken section not found. Checking for missing closing tags...');
    // Count opening and closing divs
    const openDivs = (content.match(/<div/g) || []).length;
    const closeDivs = (content.match(/<\/div>/g) || []).length;
    console.log(`Raw telemetry: Open divs: ${openDivs}, Close divs: ${closeDivs}`);
    
    if (openDivs !== closeDivs) {
        console.log('✅ Confirmed: Missing closing tags detected. Adding final closing structure.');
        content += `
    </div>
  )
}

export default App
`;
        fs.writeFileSync(filePath, content);
        console.log('✅ App.jsx repaired with correct closing tags.');
    } else {
        console.log('✅ App.jsx is already balanced.');
    }
}
NODE_REPAIR_ACTION

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
