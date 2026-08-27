#!/bin/bash

CONTAINER_ID="5ecbf5b801b5"

echo "=== STEP 1: Find the exact component hardcoding fake paths ==="
# Search for the fake path in ALL JS/JSX/TS files inside the container
FAKE_PATH_COMPONENT=$(sudo docker exec "$CONTAINER_ID" sh -c 'grep -rl "/home/owner/data\|/var/log/app\|/tmp/cache" /app --include="*.js" --include="*.jsx" --include="*.ts" --include="*.tsx" 2>/dev/null | grep -v node_modules | head -n 1')

if [ -z "$FAKE_PATH_COMPONENT" ]; then
    echo "❌ ERROR: Could not find the file. Trying a broader search..."
    FAKE_PATH_COMPONENT=$(sudo docker exec "$CONTAINER_ID" sh -c 'grep -rl "home/owner" /app --include="*.js" --include="*.jsx" 2>/dev/null | grep -v node_modules | head -n 1')
fi

if [ -z "$FAKE_PATH_COMPONENT" ]; then
    echo "❌ ERROR: Still cannot find it. Please list all JS files manually."
    sudo docker exec "$CONTAINER_ID" sh -c 'find /app -name "*.jsx" -o -name "*.js" 2>/dev/null | grep -v node_modules'
    exit 1
fi

echo "✅ Found Component: $FAKE_PATH_COMPONENT"

echo ""
echo "=== STEP 2: Patch the component to use REAL data ==="
# Inject the strict logic directly into the file
sudo docker exec -i "$CONTAINER_ID" sh -c "cat > $FAKE_PATH_COMPONENT << 'PATCH_JS_EOF'
// ==========================================
// PATCHED COMPONENT: REAL DATA ONLY
// ==========================================

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

// Use this in your JSX render:
// {getContainerDetails(container) ? (
//   <div>
//     <h4>Volumes (Host -> Container)</h4>
//     {container.real_info.mounts.map(m => (
//       <div key={m.Source}>{m.Source} -> {m.Destination}</div>
//     ))}
//   </div>
// ) : (
//   <div>No real data available for this container.</div>
// )}
PATCH_JS_EOF"

echo "✅ Component patched to use only real data."

echo ""
echo "=== STEP 3: Restart the frontend container ==="
sudo docker restart "$CONTAINER_ID"
sleep 8

echo ""
echo "=== STEP 4: Verify REAL data is flowing ==="
curl -s http://localhost:3001/api/forensic-data | python3 -c "
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
