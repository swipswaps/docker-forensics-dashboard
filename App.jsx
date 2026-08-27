import React, { useState, useEffect } from 'react'
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

  // MERGE real_info into the container objects so the UI can render it
  const safeData = {
    system_load: data.system_load || [],
    memory_usage: data.memory_usage || [],
    high_cpu_processes: data.high_cpu_processes || [],
    docker_containers: (data.docker_containers || []).map(c => ({
      ...c,
      image: c.image || 'N/A',
      real_info: c.real_info || {},
      volumes: c.real_info?.mounts || [],
      networks: c.real_info?.networks || [],
      env: c.real_info?.env || []
    })),
    all_processes: data.all_processes || [],
    total_snapshots: data.total_snapshots || 3
  }

  return (
    <div className="App">
      <header className="header">
        <h1>🔍 Forensic Investigation Dashboard</h1>
        <p>System: Fedora 43 - {safeData.total_snapshots} snapshots captured</p>
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
              <LineChart data={safeData.system_load}>
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
              <BarChart data={safeData.memory_usage}>
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
                {safeData.high_cpu_processes?.slice(0, 5).map((proc, i) => (
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
                <span className="stat-number">{safeData.docker_containers?.filter(c => c.status.includes('Up')).length || 0}</span>
                <span className="stat-label">Running</span>
              </div>
              <div className="stat-box">
                <span className="stat-number">{safeData.docker_containers?.filter(c => c.status.includes('Exited')).length || 0}</span>
                <span className="stat-label">Exited</span>
              </div>
              <div className="stat-box">
                <span className="stat-number">{safeData.docker_containers?.filter(c => c.status.includes('Created')).length || 0}</span>
                <span className="stat-label">Created</span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={100}>
              <PieChart>
                <Pie
                  data={[
                    { name: 'Running', value: safeData.docker_containers?.filter(c => c.status.includes('Up')).length || 0 },
                    { name: 'Exited', value: safeData.docker_containers?.filter(c => c.status.includes('Exited')).length || 0 },
                    { name: 'Created', value: safeData.docker_containers?.filter(c => c.status.includes('Created')).length || 0 }
                  ]}
                  cx="50%"
                  cy="50%"
                  innerRadius={20}
                  outerRadius={40}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {safeData.docker_containers?.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
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
                {safeData.docker_containers?.map((cont, i) => (
                  <tr key={i}>
                    <td><strong>{cont.name}</strong></td>
                    <td>{cont.image}</td>
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
          </div>
        </div>
      )}
    </div>
  )
}

export default App
