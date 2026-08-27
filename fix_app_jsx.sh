#!/bin/bash

CONTAINER_ID="5ecbf5b801b5"
APP_JSX="/app/src/App.jsx"

echo "=== STEP 1: Verify we are targeting the correct component ==="
# Check if App.jsx contains the fake paths
CHECK_RESULT=$(sudo docker exec "$CONTAINER_ID" sh -c 'grep -c "home/owner/data\|/var/log/app\|/tmp/cache" /app/src/App.jsx 2>/dev/null')

if [ "$CHECK_RESULT" -eq 0 ]; then
    echo "❌ ERROR: Fake paths NOT found in App.jsx. Attempting broader search..."
    sudo docker exec "$CONTAINER_ID" sh -c 'grep -rn "home/owner" /app/src/*.jsx 2>/dev/null'
    exit 1
fi

echo "✅ Confirmed: Fake paths found in App.jsx."

echo ""
echo "=== STEP 2: Surgically remove fake paths and inject REAL logic ==="
# Use Python to surgically edit the JSX file inside the container
sudo docker exec -i "$CONTAINER_ID" python3 - "$APP_JSX" << 'PY_JSX_PATCH_EOF'
import sys, re

script_path = sys.argv[1]
with open(script_path, 'r') as f:
    content = f.read()

# 1. Remove all hardcoded fake paths
content = content.replace("/home/owner/data", "")
content = content.replace("/var/log/app", "")
content = content.replace("/tmp/cache", "")

# 2. Remove hardcoded fake networks
content = content.replace("bridge: 172.17.0.2", "")
content = content.replace("overlay: 10.0.1.3", "")

# 3. Remove hardcoded fake ports
content = content.replace("Host: 3000 -> Container: 3000", "")
content = content.replace("Host: 5432 -> Container: 5432", "")

# 4. Inject the strict REAL data logic (replaces any getContainerDetails function)
strict_js = r'''
const getContainerDetails = (container) => {
  const realInfo = container.real_info;

  // STRICT CHECK: No placeholders allowed!
  if (!realInfo || Object.keys(realInfo).length === 0) {
      return null;
  }

  const hasRealData = (realInfo.mounts && realInfo.mounts.length > 0) ||
                      (realInfo.networks && realInfo.networks.length > 0) ||
                      (realInfo.env && realInfo.env.length > 0);

  if (!hasRealData) {
      return null;
  }

  return realInfo;
};
'''

# Find and replace the old function (if exists)
if "getContainerDetails" in content:
    # Replace the old function logic
    content = re.sub(r'const getContainerDetails = \(container\) => \{.*?\};', strict_js, content, flags=re.DOTALL)
else:
    # Append the new function to the top of the file
    content = strict_js + "\n" + content

# 5. Save the file
with open(script_path, 'w') as f:
    f.write(content)

print("✅ App.jsx patched successfully. Fake data removed, real data enabled.")
PY_JSX_PATCH_EOF

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
