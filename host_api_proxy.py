#!/usr/bin/env python3
"""
COMPLETE HOST API PROXY
Fetches ALL forensic data: system load, memory, processes, real Docker mounts, and directories.
Runs on the HOST (port 3001).
"""
import json, subprocess, time, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def get_system_load():
    try:
        load_avg = os.getloadavg()
        return [{"timestamp": time.strftime("%H:%M:%S"), "load_1m": load_avg[0], "load_5m": load_avg[1], "load_15m": load_avg[2]}]
    except:
        return []

def get_memory_usage():
    try:
        with open('/proc/meminfo') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])
        total_mb = meminfo.get('MemTotal', 0) // 1024
        free_mb = meminfo.get('MemFree', 0) // 1024
        used_mb = total_mb - free_mb
        return [{"timestamp": time.strftime("%H:%M:%S"), "used_mb": used_mb, "free_mb": free_mb, "total_mb": total_mb}]
    except:
        return []

def get_high_cpu_processes():
    try:
        result = subprocess.run(["ps", "aux", "--sort=-%cpu"], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')[1:]
        procs = []
        for line in lines[:10]:
            parts = line.split(None, 10)
            if len(parts) >= 11:
                procs.append({"name": parts[10][:50], "avg_cpu": float(parts[2]), "max_cpu": float(parts[2]), "avg_mem": float(parts[3])})
        return procs
    except:
        return []

def get_detected_directories():
    """Scan host directories for project folders."""
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
        except:
            continue
    return found

def get_real_docker_details(container_name):
    try:
        result = subprocess.run(["docker", "inspect", container_name], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        if not data:
            return None
        container = data[0]
        networks_obj = container.get('NetworkSettings', {}).get('Networks', {})
        networks = []
        for n_name, n_info in networks_obj.items():
            networks.append({'name': n_name, 'ip': n_info.get('IPAddress', ''), 'gateway': n_info.get('Gateway', '')})
        return {
            'mounts': container.get('Mounts', []),
            'networks': networks,
            'env': container.get('Config', {}).get('Env', []),
            'ports': container.get('NetworkSettings', {}).get('Ports', {})
        }
    except:
        return None

@app.get("/api/forensic-data")
def get_forensic_data():
    try:
        result = subprocess.run(["docker", "ps", "-a", "--format", "{{json .}}"], capture_output=True, text=True, check=True)
        raw_containers = [json.loads(line) for line in result.stdout.strip().split('\n') if line]
        containers_list = []
        for c in raw_containers:
            container_name = c.get('Names', 'unknown')
            real_info = get_real_docker_details(container_name)
            if real_info is None:
                real_info = {'mounts': [], 'networks': [], 'env': [], 'ports': []}
            containers_list.append({
                'name': container_name,
                'status': c.get('Status', ''),
                'cpu': 0.0,
                'memory': 0.0,
                'real_info': real_info
            })
        payload = {
            "total_snapshots": 3,
            "system_load": get_system_load(),
            "memory_usage": get_memory_usage(),
            "high_cpu_processes": get_high_cpu_processes(),
            "docker_containers": containers_list,
            "all_processes": [],
            "detected_directories": get_detected_directories()
        }
        return payload
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3001)
