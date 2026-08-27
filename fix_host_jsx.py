#!/usr/bin/env python3
"""
Host-side JSX repair using Python.
Reads the actual App.jsx, surgically removes the broken block, and verifies.
"""

import os
import sys
import shutil
import subprocess

# Paths
repo_dir = "/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo"
container_name = "notes-forensic-dashboard-1"
container_id = "5ecbf5b801b5"
app_jsx_host = os.path.join(repo_dir, "App.jsx")  # We will pull this to the host

# Step 1: Pull the broken App.jsx from the container (or check if mounted)
print("=== RAW TELEMETRY: Checking if container is running ===")
status = subprocess.run(
    ["sudo", "docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Status}}"],
    capture_output=True, text=True
)
print(f"Container Status: {status.stdout.strip()}")

print("\n=== RAW TELEMETRY: Pulling file to host for repair ===")
# Copy the file out of the container (even if stopped)
copy_result = subprocess.run(
    ["sudo", "docker", "cp", f"{container_id}:/app/src/App.jsx", app_jsx_host],
    capture_output=True, text=True
)
if copy_result.returncode != 0:
    print(f"❌ Could not copy file: {copy_result.stderr}")
    # Fallback: Check if file exists on host already
    if os.path.exists(app_jsx_host):
        print("✅ Found existing file on host.")
    else:
        print("❌ File not found anywhere. Cannot proceed.")
        sys.exit(1)
else:
    print("✅ File copied to host.")

# Step 2: Read and repair with Python
print("\n=== ACTION: Repairing App.jsx with Python ===")
with open(app_jsx_host, 'r') as f:
    content = f.read()

# Count the broken tags
open_divs = content.count('<div')
close_divs = content.count('</div>')
print(f"Raw Telemetry: Open <div>: {open_divs}, Close </div>: {close_divs}")

# Find and remove the broken stray `</tbody>` block
broken_marker = '      )}\n      \n                </tbody>\n              </table>\n            </div>'
if broken_marker in content:
    content = content.replace(broken_marker, '      )}\n')
    print("✅ Removed broken `</tbody>` block.")

# Ensure the file ends correctly
if not content.strip().endswith('export default App'):
    content += '\n    </div>\n  )\n}\n\nexport default App\n'
    print("✅ Added correct closing structure.")

with open(app_jsx_host, 'w') as f:
    f.write(content)

print("✅ App.jsx repaired on host.")

# Step 3: Copy the repaired file back into the container
print("\n=== ACTION: Copying repaired file back into container ===")
subprocess.run(
    ["sudo", "docker", "cp", app_jsx_host, f"{container_id}:/app/src/App.jsx"],
    capture_output=True, text=True
)
print("✅ Repaired file copied back.")

# Step 4: Start the container
print("\n=== ACTION: Starting container ===")
subprocess.run(["sudo", "docker", "start", container_id], capture_output=True, text=True)
import time
time.sleep(8)

# Step 5: Verify raw build output
print("\n=== RAW TELEMETRY: Verify JSX compiles ===")
build_result = subprocess.run(
    ["sudo", "docker", "exec", container_id, "sh", "-c", "cd /app && npx vite build 2>&1 | head -n 30"],
    capture_output=True, text=True
)
print(build_result.stdout)

# Step 6: Verify API data is flowing
print("\n=== RAW TELEMETRY: Verify API connection ===")
curl_result = subprocess.run(
    ["curl", "-s", "http://localhost:3000/api/forensic-data"],
    capture_output=True, text=True
)
try:
    import json
    data = json.loads(curl_result.stdout)
    containers = data.get('docker_containers', [])
    target = next((c for c in containers if c.get('name') == 'repo-setup-redis'), None)
    if target:
        mounts = target.get('real_info', {}).get('mounts', [])
        print(f'Container: repo-setup-redis')
        print(f'REAL Mounts found: {len(mounts)}')
        for m in mounts:
            print(f'  - {m.get("Source")} -> {m.get("Destination")}')
        print('✅ BACKEND DATA FLOWING. Refresh your browser NOW!')
except Exception as e:
    print(f"❌ API verification failed: {e}")
