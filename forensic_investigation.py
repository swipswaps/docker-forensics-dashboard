#!/usr/bin/env python3
# Forensic investigation tool - secure version with data separation
# References:
# - SQLite3 documentation: https://sqlite.org/docs.html
# - Python subprocess module: https://docs.python.org/3/library/subprocess.html
# - Docker stats API: https://docs.docker.com/engine/api/v1.41/#operation/ContainerStats

import os
import sys
import time
import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

class ForensicInvestigator:
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.environ.get('FORENSIC_DATA_DIR', './forensic_data')
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "forensic_logs.db"
        self.report_path = self.data_dir / "forensic_report.json"

    def setup_database(self):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS process_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            pid INTEGER,
            name TEXT,
            cpu REAL,
            memory REAL,
            cmdline TEXT
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS docker_containers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            container_id TEXT,
            name TEXT,
            image TEXT,
            status TEXT,
            cpu REAL,
            memory REAL
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            load_avg_1m REAL,
            load_avg_5m REAL,
            load_avg_15m REAL,
            memory_total INTEGER,
            memory_used INTEGER,
            memory_free INTEGER
        )
        ''')
        conn.commit()
        conn.close()

    def capture_processes(self):
        timestamp = datetime.now().isoformat()
        processes = []
        try:
            ps_output = subprocess.check_output(['ps', 'aux'], text=True)
            lines = ps_output.strip().split('\n')[1:]
            for line in lines:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    try:
                        pid = int(parts[1])
                        cpu = float(parts[2])
                        memory = float(parts[3])
                        name = parts[10] if len(parts) > 10 else parts[0]
                        cmdline = ' '.join(parts[10:]) if len(parts) > 10 else ''
                        processes.append({
                            'pid': pid,
                            'name': name,
                            'cpu': cpu,
                            'memory': memory,
                            'cmdline': cmdline[:200]
                        })
                    except (ValueError, IndexError):
                        continue
        except Exception as e:
            print(f"Error capturing processes: {e}")
        return timestamp, processes

    def capture_docker(self):
        timestamp = datetime.now().isoformat()
        containers = []
        try:
            docker_ps = subprocess.check_output(['docker', 'ps', '-a', '--format',
                '{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}'], text=True)
            for line in docker_ps.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) >= 4:
                    container_id = parts[0][:12]
                    name = parts[1]
                    image = parts[2]
                    status = parts[3]
                    cpu_mem = self.get_docker_stats(container_id)
                    containers.append({
                        'container_id': container_id,
                        'name': name,
                        'image': image,
                        'status': status,
                        'cpu': cpu_mem.get('cpu', 0.0),
                        'memory': cpu_mem.get('memory', 0.0)
                    })
        except Exception as e:
            print(f"Error capturing docker: {e}")
        return timestamp, containers

    def get_docker_stats(self, container_id):
        stats = {'cpu': 0.0, 'memory': 0.0}
        try:
            result = subprocess.check_output(
                ['docker', 'stats', '--no-stream', '--format', '{{.CPUPerc}}|{{.MemPerc}}', container_id],
                text=True,
                stderr=subprocess.DEVNULL
            )
            parts = result.strip().split('|')
            if len(parts) >= 2:
                cpu_str = parts[0].replace('%', '')
                mem_str = parts[1].replace('%', '')
                try:
                    stats['cpu'] = float(cpu_str)
                    stats['memory'] = float(mem_str)
                except ValueError:
                    pass
        except Exception:
            pass
        return stats

    def capture_system_metrics(self):
        timestamp = datetime.now().isoformat()
        try:
            load_avg = os.getloadavg()
            mem_info = {}
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        mem_info[key] = int(val)
            memory_total = mem_info.get('MemTotal', 0)
            memory_free = mem_info.get('MemFree', 0)
            memory_used = memory_total - memory_free - mem_info.get('Buffers', 0) - mem_info.get('Cached', 0)
            return timestamp, {
                'load_avg_1m': load_avg[0],
                'load_avg_5m': load_avg[1],
                'load_avg_15m': load_avg[2],
                'memory_total': memory_total,
                'memory_used': memory_used,
                'memory_free': memory_free
            }
        except Exception as e:
            print(f"Error capturing system metrics: {e}")
            return timestamp, {}

    def save_to_database(self, timestamp, processes, containers, metrics):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        for proc in processes:
            cursor.execute('''
            INSERT INTO process_snapshots (timestamp, pid, name, cpu, memory, cmdline)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, proc['pid'], proc['name'], proc['cpu'], proc['memory'], proc['cmdline']))
        for cont in containers:
            cursor.execute('''
            INSERT INTO docker_containers (timestamp, container_id, name, image, status, cpu, memory)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, cont['container_id'], cont['name'], cont['image'],
                  cont['status'], cont['cpu'], cont['memory']))
        cursor.execute('''
        INSERT INTO system_metrics (timestamp, load_avg_1m, load_avg_5m, load_avg_15m, memory_total, memory_used, memory_free)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, metrics.get('load_avg_1m', 0), metrics.get('load_avg_5m', 0),
              metrics.get('load_avg_15m', 0), metrics.get('memory_total', 0),
              metrics.get('memory_used', 0), metrics.get('memory_free', 0)))
        conn.commit()
        conn.close()

    def run_investigation(self):
        print("Starting forensic investigation...")
        self.setup_database()
        for i in range(3):
            print(f"Capture {i+1}/3")
            timestamp, processes = self.capture_processes()
            _, containers = self.capture_docker()
            _, metrics = self.capture_system_metrics()
            self.save_to_database(timestamp, processes, containers, metrics)
            snapshot_path = self.data_dir / f"snapshot_{i+1}_{timestamp.replace(':', '-')}.json"
            with open(snapshot_path, 'w') as f:
                json.dump({
                    'timestamp': timestamp,
                    'processes': processes,
                    'containers': containers,
                    'metrics': metrics
                }, f, indent=2)
            time.sleep(2)
        print("Forensic investigation complete")

    def generate_report(self):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        report = {
            'total_snapshots': 0,
            'processes': {},
            'docker_containers': [],
            'high_cpu_processes': [],
            'high_memory_processes': [],
            'system_load': []
        }
        cursor.execute("SELECT COUNT(DISTINCT timestamp) FROM process_snapshots")
        report['total_snapshots'] = cursor.fetchone()[0]
        cursor.execute('''
        SELECT name, AVG(cpu) as avg_cpu, AVG(memory) as avg_mem, MAX(cpu) as max_cpu
        FROM process_snapshots
        GROUP BY name
        ORDER BY avg_cpu DESC
        ''')
        high_cpu = []
        for row in cursor.fetchall():
            if row[1] > 5.0:
                high_cpu.append({'name': row[0], 'avg_cpu': row[1], 'max_cpu': row[3]})
        report['high_cpu_processes'] = high_cpu
        cursor.execute('''
        SELECT DISTINCT name, image, status, AVG(cpu) as avg_cpu, AVG(memory) as avg_mem
        FROM docker_containers
        GROUP BY container_id
        ORDER BY avg_cpu DESC
        ''')
        report['docker_containers'] = [{'name': row[0], 'image': row[1], 'status': row[2],
                                       'avg_cpu': row[3], 'avg_mem': row[4]} for row in cursor.fetchall()]
        cursor.execute('''
        SELECT timestamp, load_avg_1m, load_avg_5m, load_avg_15m
        FROM system_metrics
        ORDER BY timestamp
        ''')
        report['system_load'] = [{'timestamp': row[0], 'load_1m': row[1], 'load_5m': row[2], 'load_15m': row[3]}
                                 for row in cursor.fetchall()]
        conn.close()
        with open(self.report_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report generated: {self.report_path}")
        return report

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 forensic_investigation_secure.py <data_directory>")
        sys.exit(1)
    data_dir = sys.argv[1]
    investigator = ForensicInvestigator(data_dir)
    investigator.run_investigation()
    investigator.generate_report()
