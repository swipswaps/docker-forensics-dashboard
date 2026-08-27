#!/usr/bin/env python3
import os
import subprocess
import time

repo_dir = "/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo"
host_file = os.path.join(repo_dir, "App.jsx")
container_id = "5ecbf5b801b5"

print("=== RAW TELEMETRY: Reading current file to find exact error ===")
with open(host_file, 'r') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print("Lines 295-310 (Raw):")
for i in range(294, min(310, len(lines))):
    print(f"{i+1}: {lines[i].rstrip()}")

print("\n=== ACTION: Completely rewrite App.jsx from scratch ===")
# This is the ORIGINAL, perfectly working App.jsx code
# We are adding the REAL data rendering logic at the end
final_code = """import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import './App.css'

function App() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedView, setSelectedView] = useState('overview')

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get('/api/forensic-data')
        setData(response.data)
        setLoading(false)
      } catch (err) {
        setError(err.message)
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) return <div className="loading">Loading forensic data...</div>
  if (error) return <div className="error">Error: {error}</div>

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8']

  return (
    <div className="App">
      <header className="header">
        <h1>🔍 Forensic Investigation Dashboard</h1>
        <p>System: Fedora 43 - {data.total_snapshots || 3} snapshots captured</p>
        <div className="nav-tabs">
          <button className={selectedView === 'overview' ? 'active' : ''} onClick={() => setSelectedView('overview')}>Overview</button>
          <button className={selectedView === 'processes' ? 'active' : ''} onClick={() => setSelectedView('processes')}>Processes</button>
          <button className={selectedView === 'docker' ? 'active' : ''} onClick={() => setSelectedView('docker')}>Docker</button>
          <button className={selectedView === 'metrics' ? 'active' : ''} onClick={() => setSelectedView('metrics')}>Metrics</button>
        </div>
      </header>

      {selectedView === 'overview' && (
        <div className="grid">
          <div className="card">
            <h2>System Load Averages</h2>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={data.system_load}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis domain={[0, 2]} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="load_1m" stroke="#8884d8" name="1 min" />
                <Line type="monotone" dataKey="load_5m" stroke="#82ca9d" name="5 min" />
                <Line type="monotone" dataKey="load_15m" stroke="#ffc658" name="15 min" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h2>Memory Usage</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.memory_usage}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="used_mb" fill="#8884d8" name="Used (MB)" />
                <Bar dataKey="free_mb" fill="#82ca9d" name="Free (MB)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h2>Top CPU Processes</h2>
            <table className="process-table">
              <thead>
                <tr>
                  <th>Process</th>
                  <th>Avg CPU %</th>
                  <th>Max CPU %</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.high_cpu_processes?.slice(0, 5).map((proc, i) => (
                  <tr key={i}>
                    <td className="process-name">{proc.name.substring(0, 40)}</td>
                    <td><span className="cpu-badge">{proc.avg_cpu}%</span></td>
                    <td>{proc.max_cpu}%</td>
                    <td><span className={proc.avg_cpu > 20 ? 'status-critical' : 'status-warning'}>
                      {proc.avg_cpu > 20 ? '⚠️ Critical' : '⚠️ Warning'}
                    </span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>Docker Containers</h2>
            <div className="docker-summary">
              <div className="stat-box">
                <span className="stat-number">{data.docker_containers?.filter(c => c.status.includes('Up')).length || 0}</span>
                <span className="stat-label">Running</span>
              </div>
              <div className="stat-box">
                <span className="stat-number">{data.docker_containers?.filter(c => c.status.includes('Exited')).length || 0}</span>
                <span className="stat-label">Exited</span>
              </div>
              <div className="stat-box">
                <span className="stat-number">{data.docker_containers?.filter(c => c.status.includes('Created')).length || 0}</span>
                <span className="stat-label">Created</span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={100}>
              <PieChart>
                <Pie
                  data={[
                    { name: 'Running', value: data.docker_containers?.filter(c => c.status.includes('Up')).length || 0 },
                    { name: 'Exited', value: data.docker_containers?.filter(c => c.status.includes('Exited')).length || 0 },
                    { name: 'Created', value: data.docker_containers?.filter(c => c.status.includes('Created')).length || 0 }
                  ]}
                  cx="50%"
                  cy="50%"
                  innerRadius={20}
                  outerRadius={40}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {data.docker_containers?.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {selectedView === 'processes' && (
        <div className="grid full-width">
          <div className="card">
            <h2>All Processes by CPU Usage</h2>
            <table className="process-table full">
              <thead>
                <tr>
                  <th>Process Name</th>
                  <th>Avg CPU %</th>
                  <th>Max CPU %</th>
                  <th>Memory %</th>
                  <th>Trend</th>
                </tr>
              </thead>
              <tbody>
                {data.all_processes?.sort((a, b) => b.avg_cpu - a.avg_cpu).slice(0, 20).map((proc, i) => (
                  <tr key={i}>
                    <td className="process-name">{proc.name.substring(0, 50)}</td>
                    <td><span className="cpu-badge">{proc.avg_cpu}%</span></td>
                    <td>{proc.max_cpu}%</td>
                    <td>{proc.avg_mem}%</td>
                    <td>
                      <span className={proc.trend === 'increasing' ? 'trend-up' : proc.trend === 'decreasing' ? 'trend-down' : 'trend-stable'}>
                        {proc.trend === 'increasing' ? '📈' : proc.trend === 'decreasing' ? '📉' : '➡️'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedView === 'docker' && (
        <div className="grid full-width">
          <div className="card">
            <h2>Docker Container Details</h2>
            <table className="container-table full">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Image</th>
                  <th>Status</th>
                  <th>CPU %</th>
                  <th>Memory %</th>
                  <th>Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {data.docker_containers?.map((cont, i) => (
                  <tr key={i}>
                    <td><strong>{cont.name}</strong></td>
                    <td>{cont.image || 'N/A'}</td>
                    <td className={cont.status.includes('Up') ? 'status-up' : 'status-down'}>
                      {cont.status}
                    </td>
                    <td>{cont.cpu}%</td>
                    <td>{cont.memory}%</td>
                    <td>
                      {cont.status.includes('Exited') ? '🗑️ Remove' : 
                       cont.status.includes('Created') ? '⏳ Start' : 
                       cont.cpu > 5 ? '⚠️ Monitor' : '✅ OK'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            <h3 style={{ marginTop: '20px' }}>Container Forensics (Real Data)</h3>
            {data.docker_containers?.map((cont, i) => {
              const realInfo = cont.real_info || {};
              const mounts = realInfo.mounts || [];
              const networks = realInfo.networks || [];
              const env = realInfo.env || [];
              
              if (mounts.length === 0 && networks.length === 0 && env.length === 0) {
                return <div key={i} style={{ padding: '10px', color: '#888' }}>No forensics data available for {cont.name}</div>;
              }
              
              return (
                <div key={i} style={{ marginBottom: '20px', border: '1px solid #ddd', padding: '15px', borderRadius: '8px' }}>
                  <h4 style={{ marginBottom: '10px' }}>{cont.name} - Forensics</h4>
                  
                  {mounts.length > 0 && (
                    <div style={{ marginBottom: '10px' }}>
                      <strong>Volumes (Host → Container)</strong>
                      <ul>
                        {mounts.map((m, idx) => (
                          <li key={idx}>{m.Source} → {m.Destination} ({m.Mode || 'rw'})</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {networks.length > 0 && (
                    <div style={{ marginBottom: '10px' }}>
                      <strong>Networks</strong>
                      <ul>
                        {networks.map((n, idx) => (
                          <li key={idx}>{n.name}: {n.ip} (gateway: {n.gateway})</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {env.length > 0 && (
                    <div style={{ marginBottom: '10px' }}>
                      <strong>Environment Variables</strong>
                      <ul>
                        {env.slice(0, 5).map((e, idx) => (
                          <li key={idx}>{e}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {selectedView === 'metrics' && (
        <div className="grid full-width">
          <div className="card">
            <h2>System Metrics Over Time</h2>
            <div className="metrics-grid">
              <div className="metric-item">
                <h3>CPU Load Trend</h3>
                <ResponsiveContainer width="100%" height={150}>
                  <LineChart data={data.system_load}>
                    <XAxis dataKey="timestamp" />
                    <YAxis domain={[0, 2]} />
                    <Tooltip />
                    <Line type="monotone" dataKey="load_1m" stroke="#8884d8" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div className="metric-item">
                <h3>Memory Usage</h3>
                <ResponsiveContainer width="100%" height={150}>
                  <BarChart data={data.memory_usage}>
                    <XAxis dataKey="timestamp" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="used_mb" fill="#82ca9d" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
"""

with open(host_file, 'w') as f:
    f.write(final_code)

print("✅ App.jsx completely rewritten from scratch.")

print("\n=== ACTION: Copy clean file back to container ===")
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
