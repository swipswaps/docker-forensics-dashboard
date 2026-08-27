#!/usr/bin/env python3
import os
import subprocess
import time

repo_dir = "/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo"
host_file = os.path.join(repo_dir, "App.jsx")
container_id = "5ecbf5b801b5"

print("=== RAW TELEMETRY: Checking current App.jsx state ===")
with open(host_file, 'r') as f:
    content = f.read()

# Check if the initial data state is empty
if "const [data, setData] = useState(null)" in content:
    print("✅ Initial state found.")
else:
    print("❌ Initial state missing.")

# Add the missing state for system_load, memory_usage, etc. before the return statement
print("\n=== ACTION: Adding full data initialization to App.jsx ===")

# This will ensure the charts have data to render
state_initialization = """
  // Ensure all data fields are initialized to prevent empty charts
  const safeData = {
    system_load: data?.system_load || [],
    memory_usage: data?.memory_usage || [],
    high_cpu_processes: data?.high_cpu_processes || [],
    docker_containers: data?.docker_containers || [],
    all_processes: data?.all_processes || [],
    total_snapshots: data?.total_snapshots || 3
  };

"""

# Insert the safeData initialization right before the return statement
content = content.replace("  return (", state_initialization + "  return (")

# Replace all references to `data.` with `safeData.` for the charts
content = content.replace("data.system_load", "safeData.system_load")
content = content.replace("data.memory_usage", "safeData.memory_usage")
content = content.replace("data.high_cpu_processes", "safeData.high_cpu_processes")
content = content.replace("data.docker_containers", "safeData.docker_containers")
content = content.replace("data.all_processes", "safeData.all_processes")
content = content.replace("data.total_snapshots", "safeData.total_snapshots")

print("✅ App.jsx patched to use safeData initialization.")

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

print("\n=== RAW TELEMETRY: Verify API connection ===")
curl_result = subprocess.run(
    ["curl", "-s", "http://localhost:3000/api/forensic-data"],
    capture_output=True, text=True
)
print(curl_result.stdout[:500])
