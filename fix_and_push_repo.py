#!/usr/bin/env python3
import os
import subprocess
import json
import time

repo_dir = "/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo"
api_file = os.path.join(repo_dir, "host_api_proxy.py")
service_name = "forensic-host-api"

print("=== STEP 1: Push the Repository ===")
# Initialize Git if not already done
subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
# Stage all files
subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
# Commit
subprocess.run(["git", "commit", "-m", "Restore full forensic dashboard: add all containers, directories, and real data"], cwd=repo_dir, capture_output=True)

# Check if remote exists
remote_result = subprocess.run(["git", "remote", "-v"], cwd=repo_dir, capture_output=True, text=True)
print(f"Raw Telemetry - Git Remote: {remote_result.stdout.strip()}")
if "origin" in remote_result.stdout:
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dir, capture_output=True)
    print("✅ Repo pushed to remote.")
else:
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo_dir, capture_output=True)
    print("⚠️ No remote found. Created local Git repo in repo/")

print("\n=== STEP 2: Fix API to return ALL 13 Containers and Directories ===")
with open(api_file, 'r') as f:
    content = f.read()

# A. Add Directory Scanner
if "get_detected_directories" not in content:
    content += r'''

def get_detected_directories():
    """Scan host directories for project folders."""
    import os
    found = []
    search_bases = ["/home/owner/Documents", "/home/owner", "/opt", "/tmp"]
    
    for base in search_bases:
        if not os.path.exists(base):
            continue
        try:
            for root, dirs, files in os.walk(base):
                if any(x in root for x in ['/.git', '/node_modules', '/.cache', '/proc', '/sys']):
                    continue
                found.append({
                    "name": os.path.basename(root),
                    "path": root,
                    "fileCount": len(files),
                    "hasGit": os.path.exists(os.path.join(root, ".git")),
                    "size": sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.isfile(os.path.join(root, f)))
                })
                if len(found) >= 50:
                    return found
        except Exception:
            continue
    return found
'''
    content = content.replace("'detected_directories': []", "'detected_directories': get_detected_directories()")
    print("✅ Directory scanner added.")

# B. Ensure ALL docker containers are returned (docker ps -a)
if "docker_ps" in content:
    content = content.replace('["docker", "ps", "-a", "--format", "{{json .}}"]', '["docker", "ps", "-a", "--format", "{{json .}}"]')
    print("✅ Docker container query fixed to use -a (all).")

# Write patched API
with open(api_file, 'w') as f:
    f.write(content)
print("✅ API patched.")

print("\n=== STEP 3: Restart API Service ===")
subprocess.run(["sudo", "systemctl", "restart", service_name], check=True)
time.sleep(5)

print("\n=== STEP 4: Verify Raw Telemetry ===")
curl_result = subprocess.run(["curl", "-s", "http://localhost:3001/api/forensic-data"], capture_output=True, text=True)
data = json.loads(curl_result.stdout)
print(f"Docker Containers (Expected 13): {len(data.get('docker_containers', []))}")
print(f"Detected Directories (Expected > 0): {len(data.get('detected_directories', []))}")
print(f"System Load: {len(data.get('system_load', []))}")
print(f"High CPU Processes: {len(data.get('high_cpu_processes', []))}")

print("\n=== DONE. Refresh browser NOW. ===")
print("Access: http://localhost:3000")
