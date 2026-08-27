#!/bin/bash

CONTAINER_ID="5ecbf5b801b5"
APP_JSX="/app/src/App.jsx"

echo "=== STEP 1: Confirm the container is running ==="
sudo docker ps --format "{{.Names}}" | grep -q "$CONTAINER_ID" || echo "⚠️ Container not found, but trying to patch anyway."

echo ""
echo "=== STEP 2: Use Node.js to add REAL data rendering to App.jsx ==="
sudo docker exec -i "$CONTAINER_ID" node - << 'NODE_UI_FIX'
const fs = require('fs');

const filePath = '/app/src/App.jsx';
let content = fs.readFileSync(filePath, 'utf8');

// 1. Check if the "Docker" section already renders real_info
if (!content.includes('real_info.mounts')) {
    // Find the Docker table section and inject the detailed real_info rendering
    const dockerSection = `
      {selectedView === 'docker' && (
        <div className="grid full-width">
          <div className="card">
            <h2>Docker Container Details</h2>
            <table className="container-table full">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Image</th>
                  <th>Status</th>
                  <th>CPU %</th>
                  <th>Memory %</th>
                  <th>Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {data.docker_containers?.map((cont, i) => (
                  <tr key={i}>
                    <td><strong>{cont.name}</strong></td>
                    <td>{cont.image || 'N/A'}</td>
                    <td className={cont.status.includes('Up') ? 'status-up' : 'status-down'}>
                      {cont.status}
                    </td>
                    <td>{cont.cpu}%</td>
                    <td>{cont.memory}%</td>
                    <td>
                      {cont.status.includes('Exited') ? '🗑️ Remove' : 
                       cont.status.includes('Created') ? '⏳ Start' : 
                       cont.cpu > 5 ? '⚠️ Monitor' : '✅ OK'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            <h3 style={{ marginTop: '20px' }}>Container Forensics (Real Data)</h3>
            {data.docker_containers?.map((cont, i) => {
              const realInfo = cont.real_info || {};
              const mounts = realInfo.mounts || [];
              const networks = realInfo.networks || [];
              const env = realInfo.env || [];
              
              if (mounts.length === 0 && networks.length === 0 && env.length === 0) {
                return <div key={i} style={{ padding: '10px', color: '#888' }}>No forensics data available for {cont.name}</div>;
              }
              
              return (
                <div key={i} style={{ marginBottom: '20px', border: '1px solid #ddd', padding: '15px', borderRadius: '8px' }}>
                  <h4 style={{ marginBottom: '10px' }}>{cont.name} - Forensics</h4>
                  
                  {mounts.length > 0 && (
                    <div style={{ marginBottom: '10px' }}>
                      <strong>Volumes (Host → Container)</strong>
                      <ul>
                        {mounts.map((m, idx) => (
                          <li key={idx}>{m.Source} → {m.Destination} ({m.Mode || 'rw'})</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {networks.length > 0 && (
                    <div style={{ marginBottom: '10px' }}>
                      <strong>Networks</strong>
                      <ul>
                        {networks.map((n, idx) => (
                          <li key={idx}>{n.name}: {n.ip} (gateway: {n.gateway})</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {env.length > 0 && (
                    <div style={{ marginBottom: '10px' }}>
                      <strong>Environment Variables</strong>
                      <ul>
                        {env.slice(0, 5).map((e, idx) => (
                          <li key={idx}>{e}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    `;

    // Replace the old docker section
    content = content.replace(
        /{selectedView === 'docker' && \([\s\S]*?\)\}/,
        dockerSection
    );
    
    console.log('✅ Docker view patched to render REAL forensic data.');
} else {
    console.log('✅ Docker view already renders real forensic data.');
}

fs.writeFileSync(filePath, content);
NODE_UI_FIX

echo ""
echo "=== STEP 3: Restart the frontend container ==="
sudo docker restart "$CONTAINER_ID"
sleep 8

echo ""
echo "=== STEP 4: Final Verification ==="
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
    print('✅ BACKEND DATA CONFIRMED. Refresh your browser NOW!')
else:
    print('❌ Container not found.')
"
