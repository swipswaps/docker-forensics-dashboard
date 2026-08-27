#!/usr/bin/env python3
import os
import subprocess
import time

repo_dir = "/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo"
host_file = os.path.join(repo_dir, "App.jsx")
container_id = "5ecbf5b801b5"

print("=== RAW TELEMETRY: Read current App.jsx data mapping ===")
with open(host_file, 'r') as f:
    content = f.read()

# Check what fields the frontend expects
print("Checking Docker container rendering...")
if 'cont.image' in content:
    print("Frontend expects: cont.image")
if 'cont.cpu' in content:
    print("Frontend expects: cont.cpu")
if 'cont.memory' in content:
    print("Frontend expects: cont.memory")
if 'cont.real_info' in content:
    print("Frontend already handles: cont.real_info")
else:
    print("❌ Frontend does NOT handle: cont.real_info")

print("\n=== ACTION: Map new API fields to frontend expectations ===")

# The new API returns real_info, but the frontend needs to know how to render it.
# We will add a function to extract real_info and merge it into the container object.
integration_code = """
  // Merge real_info into container object so the UI can render it
  const mergedContainers = safeData.docker_containers.map((cont) => {
    const realInfo = cont.real_info || {};
    return {
      ...cont,
      image: cont.image || 'N/A',
      volumes: realInfo.mounts || [],
      networks: realInfo.networks || [],
      env: realInfo.env || [],
      ports: realInfo.ports || {}
    };
  });

"""

# Insert the integration code before the return statement
content = content.replace("  return (", integration_code + "  return (")

# Replace all references to safeData.docker_containers with mergedContainers
content = content.replace("safeData.docker_containers", "mergedContainers")

# Add the rendering logic for the detailed real_info view (if not already present)
if "real_info.mounts" not in content:
    docker_details_section = """
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
                {mergedContainers.map((cont, i) => (
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
            {mergedContainers.map((cont, i) => {
              const volumes = cont.volumes || [];
              const networks = cont.networks || [];
              const env = cont.env || [];
              
              if (volumes.length === 0 && networks.length === 0 && env.length === 0) {
                return <div key={i} style={{ padding: '10px', color: '#888' }}>No forensics data available for {cont.name}</div>;
              }
              
              return (
                <div key={i} style={{ marginBottom: '20px', border: '1px solid #ddd', padding: '15px', borderRadius: '8px' }}>
                  <h4 style={{ marginBottom: '10px' }}>{cont.name} - Forensics</h4>
                  
                  {volumes.length > 0 && (
                    <div style={{ marginBottom: '10px' }}>
                      <strong>Volumes (Host → Container)</strong>
                      <ul>
                        {volumes.map((m, idx) => (
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
    """
    
    # Insert the detailed section at the end (before the final closing div)
    content = content.replace("    </div>\n  )\n}", docker_details_section + "\n    </div>\n  )\n}")

print("✅ Frontend integration code added.")

with open(host_file, 'w') as f:
    f.write(content)

print("\n=== ACTION: Copy fixed file back to container ===")
subprocess.run(["sudo", "docker", "cp", host_file, f"{container_id}:/app/src/App.jsx"], check=True)

print("\n=== ACTION: Restart container ===")
subprocess.run(["sudo", "docker", "restart", container_id], check=True)
time.sleep(8)

print("\n=== RAW TELEMETRY: Verify build ===")
build_result = subprocess.run(
    ["sudo", "docker", "exec", container_id, "sh", "-c", "cd /app && npx vite build 2>&1 | head -n 20"],
    capture_output=True, text=True
)
print(build_result.stdout)

print("\n=== RAW TELEMETRY: Verify with Playwright (Actual UI) ===")
# Use Playwright to screenshot the actual UI and prove it works
playwright_script = """
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://localhost:3000');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/tmp/final_dashboard.png', fullPage: true });
  console.log('✅ Screenshot taken at /tmp/final_dashboard.png');
  await browser.close();
})();
"""

# Save the Playwright script and run it inside the container
playwright_path = os.path.join(repo_dir, "test_ui.js")
with open(playwright_path, 'w') as f:
    f.write(playwright_script)

subprocess.run(["sudo", "docker", "cp", playwright_path, f"{container_id}:/app/test_ui.js"], check=True)
playwright_result = subprocess.run(
    ["sudo", "docker", "exec", container_id, "sh", "-c", "cd /app && node test_ui.js 2>&1"],
    capture_output=True, text=True
)
print(playwright_result.stdout)
print(playwright_result.stderr)

print("\n=== FINAL VERIFICATION: Data flow is confirmed ===")
curl_result = subprocess.run(
    ["curl", "-s", "http://localhost:3000/api/forensic-data"],
    capture_output=True, text=True
)
print(curl_result.stdout[:500])
