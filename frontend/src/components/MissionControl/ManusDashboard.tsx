import { useState, useEffect } from 'react'
import { AlertCircle, CheckCircle, Clock, AlertTriangle, Loader2, RefreshCw } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

interface AgentHealth {
  name: string
  status: 'healthy' | 'degraded' | 'down' | 'unknown'
  success_rate_24h: number
  last_success: string | null
  last_failure: string | null
  is_silent_failure: boolean
  avg_response_time_ms: number | null
  success_count: number
  failure_count: number
}

interface TaskMetrics {
  total: number
  completed: number
  failed: number
  in_progress: number
  success_rate: number
}

interface DashboardMetrics {
  agents: AgentHealth[]
  tasks_24h: TaskMetrics
  silent_failures: number
}

export default function ManusDashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())

  const fetchMetrics = async () => {
    try {
      const token = localStorage.getItem('token')

      // If no token, show helpful message
      if (!token) {
        setError('Please login to view Manus AI metrics')
        setLoading(false)
        return
      }

      const response = await fetch('/api/manus/dashboard/metrics', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error('Manus API error:', response.status, errorText)
        throw new Error(`Failed to fetch metrics: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()
      setMetrics(data)
      setLastUpdate(new Date())
      setError(null)
    } catch (err: any) {
      setError(err.message || 'Failed to connect to Manus AI service')
      console.error('Failed to fetch Manus metrics:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMetrics()
    // Poll every 10 seconds (following existing pattern)
    const interval = setInterval(fetchMetrics, 10000)
    return () => clearInterval(interval)
  }, [])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="text-green-500 w-5 h-5" />
      case 'degraded':
        return <AlertTriangle className="text-yellow-500 w-5 h-5" />
      case 'down':
        return <AlertCircle className="text-red-500 w-5 h-5" />
      default:
        return <Clock className="text-gray-500 w-5 h-5" />
    }
  }

  const getStatusBadge = (status: string) => {
    const colors = {
      healthy: 'bg-green-900/50 text-green-300 border-green-700',
      degraded: 'bg-yellow-900/50 text-yellow-300 border-yellow-700',
      down: 'bg-red-900/50 text-red-300 border-red-700',
      unknown: 'bg-gray-900/50 text-gray-300 border-gray-700'
    }

    return (
      <span className={`px-2 py-1 rounded text-xs font-semibold border ${colors[status as keyof typeof colors] || colors.unknown}`}>
        {status.toUpperCase()}
      </span>
    )
  }

  const formatAgentName = (name: string) => {
    return name
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never'
    try {
      return new Date(dateStr).toLocaleString()
    } catch {
      return 'Invalid date'
    }
  }

  if (loading) {
    return (
      <div className="h-full overflow-y-auto p-8 bg-rich-navy flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-blue-400 mx-auto mb-4" />
          <div className="text-white/70 font-semibold">Loading Manus AI Dashboard...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-full overflow-y-auto p-8 bg-rich-navy">
        <div className="flex items-center justify-center h-64">
          <div className="text-center bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-8 max-w-md">
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-white mb-2">Connection Error</h2>
            <div className="text-white/70 mb-4">{error}</div>
            <p className="text-sm text-white/50 mb-6">
              Make sure the backend server is running and you're logged in.
            </p>
            <button
              onClick={fetchMetrics}
              className="px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white rounded-xl font-semibold shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-300 border border-white/20"
            >
              Retry Connection
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!metrics) return null

  // Prepare chart data
  const chartData = [
    { name: 'Completed', value: metrics.tasks_24h.completed, fill: '#10b981' },
    { name: 'Failed', value: metrics.tasks_24h.failed, fill: '#ef4444' },
    { name: 'In Progress', value: metrics.tasks_24h.in_progress, fill: '#3b82f6' }
  ]

  return (
    <div className="h-full overflow-y-auto p-8 bg-rich-navy">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2">
            Manus AI Dashboard
          </h1>
          <p className="text-white/60 text-sm font-medium">
            Last updated: {lastUpdate.toLocaleTimeString()}
          </p>
        </div>
        <button
          onClick={fetchMetrics}
          className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white rounded-xl font-semibold shadow-lg hover:shadow-xl hover:scale-105 transition-all duration-300 border border-white/20"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Silent Failures Alert */}
      {metrics.silent_failures > 0 && (
        <div className="mb-6 bg-red-900/20 border-2 border-red-500/50 rounded-xl p-4 backdrop-blur-sm shadow-lg shadow-red-500/20">
          <div className="flex items-start gap-3">
            <AlertCircle className="text-red-400 w-6 h-6 flex-shrink-0 mt-1 animate-pulse" />
            <div>
              <p className="text-red-300 font-semibold text-lg">
                ⚠️ {metrics.silent_failures} Silent Failure{metrics.silent_failures > 1 ? 's' : ''} Detected
              </p>
              <p className="text-red-400 text-sm mt-1">
                One or more agents haven't reported in their expected timeframe. Check agent health below.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Overall Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-6 shadow-xl hover:shadow-2xl hover:border-white/20 transition-all duration-300">
          <div className="text-white/60 text-sm mb-2 uppercase tracking-wider font-semibold">Total Tasks (24h)</div>
          <div className="text-4xl font-bold text-white">{metrics.tasks_24h.total}</div>
        </div>

        <div className="bg-white/5 backdrop-blur-md border border-green-500/30 rounded-xl p-6 shadow-xl hover:shadow-2xl hover:border-green-500/50 transition-all duration-300">
          <div className="text-white/60 text-sm mb-2 uppercase tracking-wider font-semibold">Success Rate</div>
          <div className="text-4xl font-bold text-green-400">
            {metrics.tasks_24h.success_rate.toFixed(1)}%
          </div>
        </div>

        <div className="bg-white/5 backdrop-blur-md border border-blue-500/30 rounded-xl p-6 shadow-xl hover:shadow-2xl hover:border-blue-500/50 transition-all duration-300">
          <div className="text-white/60 text-sm mb-2 uppercase tracking-wider font-semibold">Completed</div>
          <div className="text-4xl font-bold text-blue-400">
            {metrics.tasks_24h.completed}
          </div>
        </div>

        <div className="bg-white/5 backdrop-blur-md border border-red-500/30 rounded-xl p-6 shadow-xl hover:shadow-2xl hover:border-red-500/50 transition-all duration-300">
          <div className="text-white/60 text-sm mb-2 uppercase tracking-wider font-semibold">Failed</div>
          <div className="text-4xl font-bold text-red-400">
            {metrics.tasks_24h.failed}
          </div>
        </div>
      </div>

      {/* Task Distribution Chart */}
      <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl p-6 mb-6 shadow-xl">
        <h2 className="text-2xl font-bold text-white mb-4">Task Distribution (24h)</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <XAxis dataKey="name" stroke="#9ca3af" />
            <YAxis stroke="#9ca3af" />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1f2937',
                border: '1px solid #374151',
                borderRadius: '0.5rem',
                color: '#fff'
              }}
            />
            <Bar dataKey="value" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Agent Health Table */}
      <div className="bg-white/5 backdrop-blur-md border border-white/10 rounded-xl overflow-hidden shadow-xl">
        <div className="p-6 border-b border-white/10 bg-gradient-to-r from-white/5 to-transparent">
          <h2 className="text-2xl font-bold text-white">Agent Health Status</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 bg-white/5">
                <th className="text-left py-4 px-6 text-white/70 font-semibold uppercase tracking-wider text-sm">Agent</th>
                <th className="text-left py-4 px-6 text-white/70 font-semibold uppercase tracking-wider text-sm">Status</th>
                <th className="text-left py-4 px-6 text-white/70 font-semibold uppercase tracking-wider text-sm">Success Rate</th>
                <th className="text-left py-4 px-6 text-white/70 font-semibold uppercase tracking-wider text-sm">Last Success</th>
                <th className="text-left py-4 px-6 text-white/70 font-semibold uppercase tracking-wider text-sm">Avg Response</th>
              </tr>
            </thead>
            <tbody>
              {metrics.agents.map((agent) => (
                <tr
                  key={agent.name}
                  className={`border-b border-white/10 hover:bg-white/10 transition-colors ${agent.is_silent_failure ? 'bg-red-500/10' : ''
                    }`}
                >
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-3">
                      {getStatusIcon(agent.status)}
                      <div>
                        <div className="text-white font-medium">
                          {formatAgentName(agent.name)}
                        </div>
                        {agent.is_silent_failure && (
                          <div className="text-xs text-red-400 mt-1 flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" />
                            SILENT FAILURE
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-6">
                    {getStatusBadge(agent.status)}
                  </td>
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-2">
                      <div className="text-white font-medium">
                        {agent.success_rate_24h.toFixed(1)}%
                      </div>
                      <div className="text-xs text-gray-500">
                        ({agent.success_count}/{agent.success_count + agent.failure_count})
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-6">
                    <div className="text-gray-400 text-sm">
                      {formatDate(agent.last_success)}
                    </div>
                  </td>
                  <td className="py-4 px-6">
                    <div className="text-gray-400 text-sm">
                      {agent.avg_response_time_ms
                        ? `${(agent.avg_response_time_ms / 1000).toFixed(1)}s`
                        : 'N/A'}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
