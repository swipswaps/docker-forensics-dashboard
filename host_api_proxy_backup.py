#!/usr/bin/env python3
"""
COMPLETE HOST API PROXY
Fetches ALL forensic data: system load, memory, processes, and real Docker mounts.
Runs on the HOST (port 3001).
"""

import json
import subprocess
import time
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Allow all origins for the dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_system_load():
    try:
        load_avg = os.getloadavg()
        return [
            {
                "timestamp": time.strftime("%H:%M:%S"),
                "load_1m": load_avg[0],
                "load_5m": load_avg[1],
                "load_15m": load_avg[2]
            }
        ]
    except Exception as e:
        return []

def get_memory_usage():
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])
        
        total_mb = meminfo.get('MemTotal', 0) // 1024
        free_mb = meminfo.get('MemFree', 0) // 1024
        used_mb = total_mb - free_mb
        
        return [
            {
                "timestamp": time.strftime("%H:%M:%S"),
                "used_mb": used_mb,
                "free_mb": free_mb,
                "total_mb": total_mb
            }
        ]
    except Exception as e:
        return []

def get_high_cpu_processes():
    try:
        result = subprocess.run(
            ["ps", "aux", "--sort=-%cpu"],
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split('\n')[1:]
        processes = []
        for line in lines[:10]:
            parts = line.split(None, 10)
            if len(parts) >= 11:
                try:
                    cpu = float(parts[2])
                    mem = float(parts[3])
                    name = parts[10][:50]
                    processes.append({
                        "name": name,
                        "avg_cpu": cpu,
                        "max_cpu": cpu,
                        "avg_mem": mem
                    })
                except (ValueError, IndexError):
                    continue
        return processes
    except Exception as e:
        return []

def get_real_docker_details(container_name):
    """Uses the HOST's docker CLI to get REAL data."""
    try:
        result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        if not data:
            return None

        container = data[0]
        mounts = container.get('Mounts', [])
        networks_obj = container.get('NetworkSettings', {}).get('Networks', {})
        env = container.get('Config', {}).get('Env', [])
        ports = container.get('NetworkSettings', {}).get('Ports', {})

        networks = []
        for net_name, net_info in networks_obj.items():
            networks.append({
                'name': net_name,
                'ip': net_info.get('IPAddress', ''),
                'gateway': net_info.get('Gateway', '')
            })

        return {
            'mounts': mounts,
            'networks': networks,
            'env': env,
            'ports': ports
        }
    except Exception as e:
        print(f"Error fetching details for {container_name}: {e}")
        return None

def get_all_processes():
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split('\n')[1:]
        processes = []
        for line in lines[:20]:
            parts = line.split(None, 10)
            if len(parts) >= 11:
                try:
                    processes.append({
                        "name": parts[10][:50],
                        "avg_cpu": float(parts[2]),
                        "max_cpu": float(parts[2]),
                        "avg_mem": float(parts[3]),
                        "trend": "stable"
                    })
                except (ValueError, IndexError):
                    continue
        return processes
    except Exception as e:
        return []

@app.get("/api/forensic-data")
def get_forensic_data():
    # 1. Get the list of containers using the host's docker CLI
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{json .}}"],
            capture_output=True, text=True, check=True
        )
        raw_containers = [json.loads(line) for line in result.stdout.strip().split('\n') if line]
        
        containers_list = []
        for c in raw_containers:
            container_name = c.get('Names', 'unknown')
            status = c.get('Status', '')
            
            # Try to get CPU/Mem from stats (or set to 0 for simplicity)
            cpu = 0.0
            mem = 0.0
            
            # Get REAL Docker details from the HOST
            real_info = get_real_docker_details(container_name)
            if real_info is None:
                real_info = {'mounts': [], 'networks': [], 'env': [], 'ports': []}
            
            containers_list.append({
                'name': container_name,
                'status': status,
                'cpu': cpu,
                'memory': mem,
                'real_info': real_info
            })
            
        # Create the FULL payload
        payload = {
            "total_snapshots": 3,
            "system_load": get_system_load(),
            "memory_usage": get_memory_usage(),
            "high_cpu_processes": get_high_cpu_processes(),
            "docker_containers": containers_list,
            "all_processes": get_all_processes(),
            "detected_directories": []  # Can be filled by scanning host directories
        }
        
        return payload
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3001)


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
