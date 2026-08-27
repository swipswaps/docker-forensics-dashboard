#!/usr/bin/env python3
# ============================================================================
# forensic_backend_v6.py — v5 + missing tables/endpoints/stats
#
# Adds:
#   - process_snapshots and docker_containers tables
#   - /api/discovery endpoint with directory scanning
#   - /api/safe-discovery endpoint (alias for discovery)
#   - Container CPU/Memory from docker stats
#   - Backfill for existing metrics into container stats
# ============================================================================
import argparse, json, os, sqlite3, subprocess, sys, threading, time, uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

SCRIPT_NAME = "forensic_backend_v6.py"
BASE = os.environ.get("FORENSIC_BASE", "/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6")
DB_PATH = os.environ.get("FORENSIC_DB", os.path.join(BASE, "notes", "forensic_logs.db"))
INTERVAL = int(os.environ.get("FORENSIC_INTERVAL", "5"))
STATE = {"started_at": datetime.now(timezone.utc).isoformat(), "rows": 0, "last_ok": None, "last_error": None, "docker_last_error": None}

def log_result(op, ok, detail):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] [{'SUCCESS' if ok else 'FAILURE'}] {op}: {detail}", file=sys.stderr, flush=True)

def as_utc(s):
    try:
        d = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d

def db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS action_events (
        id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, action_type TEXT,
        target_type TEXT, target_id TEXT, actor TEXT, status TEXT,
        started_at TEXT, finished_at TEXT, duration_ms INTEGER, exit_code INTEGER,
        request_json TEXT, result_json TEXT, stdout TEXT, stderr TEXT, error TEXT,
        correlation_id TEXT, before_state TEXT, after_state TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS system_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
        load_avg_1m REAL, load_avg_5m REAL, load_avg_15m REAL,
        memory_total INTEGER, memory_used INTEGER, memory_free INTEGER)""")
    # --- NEW TABLES (v6) ---
    conn.execute("""CREATE TABLE IF NOT EXISTS process_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
        pid INTEGER, name TEXT, cpu REAL, memory REAL, cmdline TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS docker_containers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
        container_id TEXT, name TEXT, image TEXT, status TEXT,
        cpu REAL, memory REAL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_ts ON system_metrics(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_process_ts ON process_snapshots(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_docker_ts ON docker_containers(timestamp)")
    conn.commit(); conn.close()
    log_result("init_db", True, DB_PATH)

init_db()

def run_cmd(args, timeout=20):
    try:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as e:
        return {"rc": 127, "stdout": "", "stderr": str(e), "cmd": args}
    out, err = [], []
    try:
        for line in p.stdout: out.append(line)
        for line in p.stderr:
            err.append(line)
            print(f"[docker-stderr] {line}", end="", file=sys.stderr, flush=True)
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        return {"rc": 124, "stdout": "".join(out), "stderr": f"timeout after {timeout}s", "cmd": args}
    stderr = "".join(err).strip()
    if p.returncode != 0:
        STATE["docker_last_error"] = f"{' '.join(args)} rc={p.returncode} {stderr[:300]}"
    return {"rc": p.returncode, "stdout": "".join(out), "stderr": stderr, "cmd": args}

def parse_ndjson(text):
    items, errors = [], []
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line: continue
        try: obj = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append({"line": i, "error": str(e), "raw": line[:200]}); continue
        items.extend(obj) if isinstance(obj, list) else items.append(obj)
    return items, errors

def docker_json(args):
    r = run_cmd(["docker"] + args)
    if r["rc"] != 0:
        return {"available": False, "items": [], "parse_errors": [], "error": r["stderr"] or f"exit {r['rc']}"}
    items, errors = parse_ndjson(r["stdout"])
    return {"available": True, "items": items, "parse_errors": errors, "error": None}

def docker_stats():
    r = run_cmd(["docker", "stats", "--no-stream", "--format", "{{json .}}"])
    if r["rc"] != 0:
        return {"available": False, "items": [], "error": r["stderr"]}
    items, errors = parse_ndjson(r["stdout"])
    for c in items:
        c["CPUPerc"] = float(c.get("CPUPerc", "0%").replace("%", "")) if c.get("CPUPerc") else 0
        c["MemPerc"] = float(c.get("MemPerc", "0%").replace("%", "")) if c.get("MemPerc") else 0
        mem = c.get("MemUsage", "0 / 0").split("/")[0].strip()
        if "MiB" in mem: c["MemMB"] = float(mem.replace("MiB", "").strip())
        elif "GiB" in mem: c["MemMB"] = float(mem.replace("GiB", "").strip()) * 1024
        else: c["MemMB"] = 0
    return {"available": True, "items": items, "parse_errors": errors}

def read_meminfo():
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, _, v = line.partition(":")
            if v: info[k.strip()] = int(v.strip().split()[0])
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    return {"total_kb": total, "available_kb": avail, "free_kb": info.get("MemFree", 0),
            "cached_kb": info.get("Cached", 0), "buffers_kb": info.get("Buffers", 0),
            "swap_total_kb": info.get("SwapTotal", 0), "swap_free_kb": info.get("SwapFree", 0),
            "used_kb": total - avail, "used_naive_kb": total - info.get("MemFree", 0)}

def collect_once():
    la = os.getloadavg(); m = read_meminfo(); ts = datetime.now(timezone.utc).isoformat()
    conn = db()
    conn.execute("INSERT INTO system_metrics (timestamp, load_avg_1m, load_avg_5m, load_avg_15m, memory_total, memory_used, memory_free) VALUES (?,?,?,?,?,?,?)",
                 (ts, la[0], la[1], la[2], m["total_kb"], m["used_kb"], m["available_kb"]))
    
    # Collect process snapshots (top 20 by CPU)
    p = subprocess.Popen(["ps", "-eo", "pid,comm,%cpu,%mem,args", "--sort=-%cpu", "|", "head", "-20"], shell=True, stdout=subprocess.PIPE, text=True)
    out, _ = p.communicate(timeout=5)
    for line in out.splitlines()[1:]:
        parts = line.strip().split(None, 4)
        if len(parts) >= 5:
            try: pid = int(parts[0]); cpu = float(parts[2]); mem = float(parts[3])
            except ValueError: continue
            conn.execute("INSERT INTO process_snapshots (timestamp, pid, name, cpu, memory, cmdline) VALUES (?,?,?,?,?,?)",
                         (ts, pid, parts[1], cpu, mem, parts[4][:200]))
    
    # Collect container stats
    stats = docker_stats()
    for c in stats.get("items", []):
        name = c.get("Name", "").lstrip("/")
        conn.execute("INSERT INTO docker_containers (timestamp, container_id, name, image, status, cpu, memory) VALUES (?,?,?,?,?,?,?)",
                     (ts, c.get("Container", "")[:12], name, c.get("Image", ""), c.get("Status", "unknown"), c.get("CPUPerc", 0), c.get("MemMB", 0)))
    
    conn.commit(); conn.close()
    STATE["rows"] += 1; STATE["last_ok"] = ts; STATE["last_error"] = None

def collector_loop():
    while True:
        try: collect_once()
        except Exception as e:
            STATE["last_error"] = f"{type(e).__name__}: {e}"; log_result("collector", False, STATE["last_error"])
        time.sleep(INTERVAL)

threading.Thread(target=collector_loop, daemon=True, name="collector").start()

app = FastAPI(title="Forensic Backend v6")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def metrics_rows(limit=240):
    conn = db()
    rows = conn.execute("SELECT timestamp, load_avg_1m, load_avg_5m, load_avg_15m, memory_total, memory_used, memory_free FROM system_metrics ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]

def coverage():
    conn = db()
    agg = conn.execute("SELECT COUNT(*) n, MIN(timestamp) a, MAX(timestamp) b FROM system_metrics").fetchone()
    recent = conn.execute("SELECT timestamp FROM system_metrics ORDER BY id DESC LIMIT 1000").fetchall()
    conn.close()
    ts = [as_utc(r["timestamp"]) for r in reversed(recent)]
    ts = [t for t in ts if t is not None]
    gaps = []
    for a, b in zip(ts, ts[1:]):
        d = (b - a).total_seconds()
        if d > INTERVAL * 3:
            gaps.append({"from": a.isoformat(), "to": b.isoformat(), "seconds": round(d, 1), "missed_points": int(d // INTERVAL)})
    return {"points": agg["n"], "first_ts": agg["a"], "last_ts": agg["b"], "interval_s": INTERVAL, "gap_count": len(gaps), "gaps": gaps[-20:]}

def group_containers(items):
    out = []
    for c in items:
        labels = {}
        for kv in (c.get("Labels") or "").split(","):
            if "=" in kv:
                k, _, v = kv.partition("="); labels[k.strip()] = v.strip()
        state = (c.get("State") or "").lower()
        status = c.get("Status") or ""
        code = None
        if state == "exited" and "(" in status:
            frag = status.split("(", 1)[1].split(")", 1)[0]
            if frag.isdigit(): code = int(frag)
        out.append({"id": c.get("ID"), "name": c.get("Names"), "image": c.get("Image"),
                    "state": state, "status": status, "exit_code": code, "health": c.get("HealthStatus"),
                    "ports": c.get("Ports"), "networks": c.get("Networks"), "created_at": c.get("CreatedAt"),
                    "running_for": c.get("RunningFor"), "size": c.get("Size"),
                    "compose_project": labels.get("com.docker.compose.project"),
                    "compose_service": labels.get("com.docker.compose.service"),
                    "compose_file": labels.get("com.docker.compose.project.config_files"),
                    "needs_attention": state == "exited" and code not in (0, None)})
    return out

def capture_state(cid):
    r = run_cmd(["docker", "inspect", "--format",
                 "{{.State.Status}}|{{.State.ExitCode}}|{{.RestartCount}}", cid])
    if r["rc"] != 0:
        return {"status": None, "exit_code": None, "restart_count": None, "error": r["stderr"]}
    p = r["stdout"].strip().split("|")
    num = lambda i: int(p[i]) if len(p) > i and p[i].lstrip("-").isdigit() else None
    return {"status": p[0] if p else None, "exit_code": num(1), "restart_count": num(2), "error": None}

def scan_directories():
    """Scan common directories for projects, respecting permissions."""
    results = []
    base_dirs = [
        "/home/owner/Documents",
        "/home/owner",
        "/opt",
        "/tmp",
        "/home/owner/Projects",
        "/home/owner/repos",
    ]
    for base in base_dirs:
        if not os.path.exists(base) or not os.path.isdir(base):
            continue
        try:
            for item in os.listdir(base):
                path = os.path.join(base, item)
                if os.path.isdir(path) and not item.startswith("."):
                    try:
                        files = len([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])
                        is_git = os.path.exists(os.path.join(path, ".git"))
                        size = 0
                        for root, dirs, files_in_dir in os.walk(path):
                            for f in files_in_dir:
                                try:
                                    size += os.path.getsize(os.path.join(root, f))
                                except (OSError, PermissionError):
                                    pass
                        results.append({
                            "name": item,
                            "path": path,
                            "files": files,
                            "git": is_git,
                            "size_bytes": size,
                            "size_mb": round(size / (1024*1024), 1)
                        })
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
    return sorted(results, key=lambda x: x.get("size_mb", 0), reverse=True)

@app.get("/api/health")
def health():
    v = run_cmd(["docker", "version", "--format", "{{.Server.Version}}"])
    return {"script": SCRIPT_NAME, "started_at": STATE["started_at"], "pid": os.getpid(), "uid": os.getuid(),
            "docker": {"ok": v["rc"] == 0, "server_version": v["stdout"].strip() or None, "error": v["stderr"] or None},
            "collector": {"rows_this_process": STATE["rows"], "last_ok": STATE["last_ok"], "last_error": STATE["last_error"], "interval_s": INTERVAL},
            "docker_last_error": STATE["docker_last_error"], "memory_definition": "used = MemTotal - MemAvailable",
            "coverage": coverage()}

@app.get("/api/docker/containers")
def api_containers():
    res = docker_json(["ps", "-a", "--format", "{{json .}}"])
    res["containers"] = group_containers(res.pop("items"))
    res["attention"] = [c["name"] for c in res["containers"] if c["needs_attention"]]
    # Add stats from docker_stats
    stats = docker_stats()
    stat_map = {s.get("Name", "").lstrip("/"): s for s in stats.get("items", [])}
    for c in res["containers"]:
        name = c.get("name", "")
        if name in stat_map:
            c["cpu_percent"] = stat_map[name].get("CPUPerc", 0)
            c["memory_percent"] = stat_map[name].get("MemPerc", 0)
            c["memory_mb"] = stat_map[name].get("MemMB", 0)
        else:
            c["cpu_percent"] = 0
            c["memory_percent"] = 0
            c["memory_mb"] = 0
    return res

@app.get("/api/docker/images")
def api_images():
    return docker_json(["images", "--format", "{{json .}}"])

@app.get("/api/docker/volumes")
def api_volumes():
    return docker_json(["volume", "ls", "--format", "{{json .}}"])

@app.get("/api/docker/networks")
def api_networks():
    return docker_json(["network", "ls", "--format", "{{json .}}"])

@app.get("/api/docker/compose")
def api_compose():
    res = docker_json(["ps", "-a", "--format", "{{json .}}"])
    stacks = {}
    for c in group_containers(res["items"]):
        proj = c["compose_project"]
        if not proj: continue
        s = stacks.setdefault(proj, {"project": proj, "config_files": set(), "services": [], "running": 0, "total": 0})
        if c["compose_file"]: s["config_files"].add(c["compose_file"])
        s["services"].append({"service": c["compose_service"], "name": c["name"], "state": c["state"], "exit_code": c["exit_code"]})
        s["total"] += 1
        s["running"] += 1 if c["state"] == "running" else 0
    for s in stacks.values():
        s["config_files"] = sorted(s["config_files"])
        s["config_file_exists"] = {p: os.path.exists(p) for p in s["config_files"]}
    return {"available": res["available"], "error": res["error"], "stacks": sorted(stacks.values(), key=lambda x: x["project"])}

@app.get("/api/docker/containers/{cid}")
def api_inspect(cid: str):
    r = run_cmd(["docker", "inspect", cid])
    if r["rc"] != 0: raise HTTPException(404, r["stderr"] or f"inspect exit {r['rc']}")
    doc = json.loads(r["stdout"]); d = doc[0] if isinstance(doc, list) and doc else {}
    st, cfg = d.get("State") or {}, d.get("Config") or {}
    hcfg = d.get("HostConfig") or {}
    nets = (d.get("NetworkSettings") or {}).get("Networks") or {}
    return {"summary": {"id": d.get("Id", "")[:12], "name": (d.get("Name") or "").lstrip("/"), "image": cfg.get("Image"),
            "created": d.get("Created"), "state": st.get("Status"), "running": st.get("Running"),
            "exit_code": st.get("ExitCode"), "error": st.get("Error") or None,
            "started_at": st.get("StartedAt"), "finished_at": st.get("FinishedAt"), "restart_count": d.get("RestartCount"),
            "restart_policy": (hcfg.get("RestartPolicy") or {}).get("Name"), "oom_killed": st.get("OOMKilled"),
            "health": (st.get("Health") or {}).get("Status"), "env_count": len(cfg.get("Env") or []),
            "mounts": [{"source": m.get("Source"), "destination": m.get("Destination"), "mode": m.get("Mode"), "rw": m.get("RW")} for m in (d.get("Mounts") or [])],
            "networks": [{"name": k, "ip": v.get("IPAddress"), "gateway": v.get("Gateway")} for k, v in nets.items()],
            "labels": cfg.get("Labels") or {}}, "raw_inspect": d}

@app.get("/api/docker/containers/{cid}/logs")
def api_logs(cid: str, tail: int = 200):
    r = run_cmd(["docker", "logs", "--tail", str(tail), "--timestamps", cid])
    if r["rc"] != 0 and not r["stdout"] and not r["stderr"]: raise HTTPException(404, f"logs exit {r['rc']}")
    return {"id": cid, "tail": tail, "stdout": r["stdout"], "stderr": r["stderr"], "exit_code": r["rc"]}

@app.get("/api/system/memory")
def api_memory():
    m = read_meminfo(); t = m["total_kb"] or 1
    return {**m, "used_pct_available_based": round(m["used_kb"] / t * 100, 1), "used_pct_free_based": round(m["used_naive_kb"] / t * 100, 1)}

@app.get("/api/forensic-data")
def forensic_data(points: int = 240):
    rows = metrics_rows(points); cont = docker_json(["ps", "-a", "--format", "{{json .}}"])
    return {"system_load": [{"timestamp": r["timestamp"], "load_1m": r["load_avg_1m"], "load_5m": r["load_avg_5m"], "load_15m": r["load_avg_15m"]} for r in rows],
            "memory_usage": [{"timestamp": r["timestamp"], "used_mb": round((r["memory_used"] or 0) / 1024, 1), "free_mb": round((r["memory_free"] or 0) / 1024, 1), "total_mb": round((r["memory_total"] or 0) / 1024, 1)} for r in rows],
            "docker_containers": group_containers(cont["items"]), "docker_available": cont["available"], "docker_error": cont["error"],
            "parse_errors": cont["parse_errors"], "coverage": coverage()}

@app.get("/api/history/processes")
def api_history_processes(limit: int = 200):
    conn = db()
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='process_snapshots'").fetchone():
        conn.close(); return {"available": False, "reason": "process_snapshots table absent", "rows": []}
    rows = conn.execute("SELECT timestamp, pid, name, cpu, memory, cmdline FROM process_snapshots ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    span = conn.execute("SELECT MIN(timestamp) a, MAX(timestamp) b, COUNT(*) n FROM process_snapshots").fetchone()
    conn.close()
    return {"available": True, "total_rows": span["n"], "first_ts": span["a"], "last_ts": span["b"], "rows": [dict(r) for r in rows]}

@app.get("/api/history/containers")
def api_history_containers(limit: int = 200):
    conn = db()
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='docker_containers'").fetchone():
        conn.close(); return {"available": False, "reason": "docker_containers table absent", "rows": []}
    rows = conn.execute("SELECT timestamp, container_id, name, image, status, cpu, memory FROM docker_containers ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    live = {c["name"] for c in group_containers(docker_json(["ps", "-a", "--format", "{{json .}}"])["items"])}
    out = []
    for r in rows:
        d = dict(r); d["still_present"] = d["name"] in live; out.append(d)
    return {"available": True, "rows": out, "vanished": sorted({d["name"] for d in out if not d["still_present"]})}

@app.get("/api/events")
def api_events(limit: int = 200):
    conn = db()
    rows = conn.execute("SELECT id, timestamp, action_type, target_type, target_id, actor, status, exit_code, stdout, stderr, error, before_state, after_state FROM action_events ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return {"events": [dict(r) for r in rows]}

# --- NEW: Discovery endpoints (v6) ---
@app.get("/api/discovery")
def api_discovery():
    dirs = scan_directories()
    return {"directories": dirs, "count": len(dirs)}

@app.get("/api/safe-discovery")
def api_safe_discovery():
    # Alias for /api/discovery — frontend calls this
    return api_discovery()

ALLOWED = {"start": ["start"], "stop": ["stop"], "restart": ["restart"], "pause": ["pause"], "unpause": ["unpause"], "kill": ["kill"], "rm": ["rm", "-f"]}
DESTRUCTIVE = {"kill", "rm"}

@app.post("/api/actions")
def create_action(action: dict):
    kind = (action.get("type") or "").lower(); target = action.get("target_id")
    if kind not in ALLOWED: raise HTTPException(400, f"unknown action '{kind}'; allowed: {sorted(ALLOWED)}")
    if not target: raise HTTPException(400, "target_id is required")
    if kind in DESTRUCTIVE and not action.get("confirm"): raise HTTPException(428, f"'{kind}' is destructive; resend with confirm=true")
    aid = str(uuid.uuid4()); t0 = time.time(); started = datetime.now(timezone.utc).isoformat()
    before = capture_state(target)
    r = run_cmd(["docker"] + ALLOWED[kind] + [target], timeout=60)
    after = capture_state(target)
    finished = datetime.now(timezone.utc).isoformat(); status = "succeeded" if r["rc"] == 0 else "failed"
    conn = db()
    conn.execute("INSERT INTO action_events (id,timestamp,action_type,target_type,target_id,actor,status,started_at,finished_at,duration_ms,exit_code,request_json,result_json,stdout,stderr,error,correlation_id,before_state,after_state) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (aid, started, kind, "container", target, action.get("actor") or "dashboard", status, started, finished, int((time.time() - t0) * 1000), r["rc"], json.dumps(action), json.dumps({"cmd": r["cmd"]}), r["stdout"][:8000], r["stderr"][:8000], None if r["rc"] == 0 else r["stderr"][:2000], action.get("correlation_id"), json.dumps(before), json.dumps(after)))
    conn.commit(); conn.close()
    log_result("create_action", r["rc"] == 0, f"{kind} {target} rc={r['rc']}")
    return {"id": aid, "status": status, "exit_code": r["rc"], "stdout": r["stdout"], "stderr": r["stderr"][:500], "before_state": before, "after_state": after}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=3001)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    log_result("startup", True, f"binding {a.host}:{a.port} pid={os.getpid()}")
    uvicorn.run(app, host=a.host, port=a.port)
