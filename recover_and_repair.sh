#!/bin/bash

echo "=== RAW TELEMETRY: Check Docker Status ==="
sudo docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep "notes-forensic-dashboard"

echo ""
echo "=== ACTION: Start the container ==="
sudo docker start 5ecbf5b801b5
sleep 5

echo ""
echo "=== RAW TELEMETRY: Confirm container is running ==="
sudo docker ps --format "{{.Names}} - {{.Status}}" | grep "notes-forensic-dashboard"

echo ""
echo "=== ACTION: Read the current raw file size ==="
sudo docker exec 5ecbf5b801b5 wc -l /app/src/App.jsx

echo ""
echo "=== ACTION: Use Node.js to surgically repair the JSX structure ==="
sudo docker exec -i 5ecbf5b801b5 node - << 'NODE_REPAIR'
const fs = require('fs');

const filePath = '/app/src/App.jsx';
const content = fs.readFileSync(filePath, 'utf8');

// 1. Count open/close divs (raw telemetry)
const openDivs = (content.match(/<div/g) || []).length;
const closeDivs = (content.match(/<\/div>/g) || []).length;
console.log(`Raw Telemetry: Open <div>: ${openDivs}, Close </div>: ${closeDivs}`);

// 2. Find the broken duplicate section
const metricsIndex = content.indexOf('{selectedView === \'metrics\' && (');
const brokenIndex = content.indexOf('Container Forensics (Real Data)');

if (brokenIndex > -1 && metricsIndex > -1 && brokenIndex > metricsIndex) {
    // Remove everything after the metrics section
    content = content.substring(0, metricsIndex);
    
    // Add the correct, balanced ending
    const ending = `
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

    fs.writeFileSync(filePath, content + ending);
    console.log('✅ Repaired: Removed broken duplicate section.');
} else {
    // If no broken section, just add missing tags
    const fixedContent = content + `
    </div>
  )
}

export default App
`;
    fs.writeFileSync(filePath, fixedContent);
    console.log('✅ Repaired: Added missing closing tags.');
}
NODE_REPAIR

echo ""
echo "=== RAW TELEMETRY: Verify JSX compiles ==="
sudo docker exec 5ecbf5b801b5 sh -c "cd /app && npx vite build 2>&1 | head -n 30"

echo ""
echo "=== RAW TELEMETRY: Final Restart ==="
sudo docker restart 5ecbf5b801b5
sleep 8

echo ""
echo "=== RAW TELEMETRY: Final API Check ==="
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
