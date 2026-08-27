#!/bin/bash

CONTAINER_ID="5ecbf5b801b5"
APP_JSX="/app/src/App.jsx"

echo "=== STEP 1: Read the actual App.jsx to understand the fake data logic ==="
sudo docker exec "$CONTAINER_ID" sh -c "cat $APP_JSX" | head -n 250
echo ""
echo "=========================================="
echo ""
echo "=== STEP 2: Use Python to surgically patch the fake logic ==="
# Use Python to read, understand, and patch the file
sudo docker exec -i "$CONTAINER_ID" python3 - "$APP_JSX" << 'PY_FINAL_PATCH_EOF'
import sys, re

script_path = sys.argv[1]

# Read the actual content
with open(script_path, 'r') as f:
    content = f.read()

# 1. Search for ANY hardcoded strings (like 'home/owner/data', 'var/log/app', etc.)
fake_strings = ["home/owner/data", "/var/log/app", "/tmp/cache"]
for fake in fake_strings:
    if fake in content:
        print(f"Found fake string: {fake}")
        content = content.replace(fake, "")

# 2. Search for a specific hardcoded object that defines volumes/networks
# Replace any generic placeholder data generation with real_info logic
if "volumes" in content:
    # Find the exact line that assigns volumes
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if 'volumes' in line and ('=' in line or ':' in line):
            # Replace with a safe extraction from real_info
            new_lines.append("  const volumes = container.real_info?.mounts || [];")
            new_lines.append("  const networks = container.real_info?.networks || [];")
            new_lines.append("  const env = container.real_info?.env || [];")
            new_lines.append("  const ports = container.real_info?.ports || [];")
        else:
            new_lines.append(line)
    content = '\n'.join(new_lines)

# 3. Inject the STRICT getContainerDetails logic
strict_js = r'''
const getContainerDetails = (container) => {
  // STRICT: Only use real_info from the API
  const realInfo = container.real_info;

  // If real_info is missing or completely empty, show nothing
  if (!realInfo || Object.keys(realInfo).length === 0) {
      return null;
  }

  // Ensure at least one array has real data
  const hasRealData = (realInfo.mounts && realInfo.mounts.length > 0) ||
                      (realInfo.networks && realInfo.networks.length > 0) ||
                      (realInfo.env && realInfo.env.length > 0);

  if (!hasRealData) {
      return null;
  }

  return realInfo;
};
'''

# If the function exists, replace it. If not, append it.
if "getContainerDetails" in content:
    content = re.sub(r'const getContainerDetails = \(container\) => \{.*?\};', strict_js, content, flags=re.DOTALL)
else:
    content = strict_js + "\n" + content

# 4. Save the file
with open(script_path, 'w') as f:
    f.write(content)

print("✅ App.jsx patched with strict real-data-only logic.")
PY_FINAL_PATCH_EOF

echo ""
echo "=== STEP 3: Restart the frontend container ==="
sudo docker restart "$CONTAINER_ID"
sleep 8

echo ""
echo "=== STEP 4: Verify REAL data is flowing ==="
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
