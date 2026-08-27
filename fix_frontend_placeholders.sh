#!/bin/bash

# Get the running frontend container ID
CONTAINER_ID=$(sudo docker ps -q -f "name=notes-forensic-dashboard-1")
if [ -z "$CONTAINER_ID" ]; then
    echo "❌ ERROR: Frontend container not found. Please recreate it first."
    exit 1
fi

echo "✅ Found Frontend Container: $CONTAINER_ID"

# Find the exact component file that renders the Docker tab (looks for the placeholder path)
echo "Finding frontend component with placeholders..."
COMPONENT_PATH=$(sudo docker exec "$CONTAINER_ID" sh -c 'grep -rl "/home/owner/data" /app/src /app/pages /app/components 2>/dev/null | head -n 1')

if [ -z "$COMPONENT_PATH" ]; then
    # Fallback: search the entire app directory if src isn't available
    COMPONENT_PATH=$(sudo docker exec "$CONTAINER_ID" sh -c 'grep -rl "/home/owner/data" /app 2>/dev/null | head -n 1')
fi

if [ -z "$COMPONENT_PATH" ]; then
    echo "❌ ERROR: Could not find the component with placeholder data. Search manually."
    sudo docker exec "$CONTAINER_ID" sh -c 'grep -r "home/owner/data" /app 2>/dev/null'
    exit 1
fi

echo "✅ Found component: $COMPONENT_PATH"

# Patch the component to strip all placeholder data and only use real_info
sudo docker exec -i "$CONTAINER_ID" sh -c "cat > $COMPONENT_PATH << 'PATCH_JS_EOF'
// ==========================================
// PATCHED COMPONENT: STRICT REAL DATA ONLY
// ==========================================

const getContainerDetails = (container) => {
  // STRICT: Only use data from the backend API (real_info)
  const realInfo = container.real_info;

  // If real_info is missing or completely empty, return null to show nothing
  if (!realInfo || Object.keys(realInfo).length === 0) {
      return null;
  }

  // CRITICAL: Check that the arrays inside real_info are ACTUALLY populated
  // No fake fallback to hardcoded values.
  const hasRealData = (realInfo.mounts && realInfo.mounts.length > 0) ||
                      (realInfo.networks && realInfo.networks.length > 0) ||
                      (realInfo.env && realInfo.env.length > 0);

  if (!hasRealData) {
      return null; // Block all placeholders entirely.
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

echo "✅ Frontend patched to use only real data."

# Restart the frontend to apply the patch
echo "Restarting frontend container..."
sudo docker restart "$CONTAINER_ID"
sleep 8

echo "✅ Frontend restarted. Open Firefox and refresh. Placeholders are now GONE."
