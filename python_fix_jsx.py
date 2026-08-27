#!/usr/bin/env python3
import os
import subprocess
import time

repo_dir = "/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo"
host_file = os.path.join(repo_dir, "App.jsx")
container_id = "5ecbf5b801b5"

print("=== RAW TELEMETRY: Checking current file structure ===")
with open(host_file, 'r') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print(f"Lines 265-275 (Raw):")
for i in range(264, min(275, len(lines))):
    print(f"{i+1}: {lines[i].rstrip()}")

print("\n=== ACTION: Surgically remove broken lines ===")
# Lines 269 and 270 are broken (0-indexed: 268 and 269)
# We will remove lines 268-270 (0-indexed) which are the broken closing tags
# Keep the structure clean by removing the broken block
new_lines = []
for i, line in enumerate(lines):
    # Skip lines 269, 270, 271 (1-indexed)
    if i + 1 in [269, 270, 271]:
        continue
    new_lines.append(line)

# Ensure only one 'export default App' at the end
# Find and remove any duplicate export lines
clean_lines = []
export_count = 0
for line in new_lines:
    if 'export default App' in line:
        export_count += 1
        if export_count == 1:
            clean_lines.append(line)
    else:
        clean_lines.append(line)

print(f"Total lines after removal: {len(clean_lines)}")

print("\n=== ACTION: Write clean file ===")
with open(host_file, 'w') as f:
    f.writelines(clean_lines)

print("✅ File written to host.")

print("\n=== RAW TELEMETRY: Verify cleaned file ===")
with open(host_file, 'r') as f:
    content = f.read()
print(f"Total lines: {len(content.splitlines())}")
print(f"Contains '</tbody>' broken block? {'</tbody>\\n              </table>' in content}")
print(f"Contains 'export default App': {content.count('export default App')} times")

print("\n=== ACTION: Copy cleaned file back to container ===")
subprocess.run(["sudo", "docker", "cp", host_file, f"{container_id}:/app/src/App.jsx"], check=True)

print("\n=== ACTION: Restart container ===")
subprocess.run(["sudo", "docker", "restart", container_id], check=True)
time.sleep(8)

print("\n=== RAW TELEMETRY: Verify build ===")
build_result = subprocess.run(
    ["sudo", "docker", "exec", container_id, "sh", "-c", "cd /app && npx vite build 2>&1 | head -n 30"],
    capture_output=True, text=True
)
print(build_result.stdout)

print("\n=== RAW TELEMETRY: Verify API ===")
curl_result = subprocess.run(
    ["curl", "-s", "http://localhost:3000/api/forensic-data"],
    capture_output=True, text=True
)
print(curl_result.stdout[:500])
