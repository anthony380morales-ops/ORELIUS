import { useState, useEffect } from 'react'
import { systemApi } from '../../services/api'
import type { SystemStatus, SystemMetrics } from '../../types'
import SecurityScore from './SecurityScore'
import KanbanBoard from './KanbanBoard'

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    try {
      const [statusData, metricsData] = await Promise.all([
        systemApi.getStatus(),
        systemApi.getMetrics(),
      ])
      setStatus(statusData)
      setMetrics(metricsData)
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error)
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    // Auto-refresh every 10 seconds
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-navy-950">
        <div className="text-center">
          <div className="text-4xl mb-4 animate-pulse">🚀</div>
          <div className="text-white animate-pulse">Initializing Mission Control...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-8 bg-navy-950 relative">
      {/* Header with glowing effect */}
      <div className="max-w-7xl mx-auto relative z-10">
        <div className="mb-8">
          <div className="flex items-center gap-4 mb-3">
            <div className="text-5xl animate-float">🚀</div>
            <div>
              <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">
                O.R.E.I.L.U.S. MISSION CONTROL
              </h1>
              <p className="text-navy-300">Strategic Command Center • Real-time System Intelligence</p>
            </div>
          </div>
        </div>

        {/* System Status Banner */}
        <div className={`mb-8 rounded-lg border-2 p-6 relative overflow-hidden ${
          status?.status === 'operational'
            ? 'border-green-500 bg-gradient-to-r from-green-900/20 to-green-800/10'
            : 'border-red-500 bg-gradient-to-r from-red-900/20 to-red-800/10'
        }`}>
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-pulse-slow" />
          <div className="relative z-10 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`h-4 w-4 rounded-full ${
                status?.status === 'operational' ? 'bg-green-500 animate-pulse' : 'bg-red-500 animate-pulse'
              }`} />
              <div>
                <div className="text-sm text-navy-300">System Status</div>
                <div className={`text-2xl font-bold ${
                  status?.status === 'operational' ? 'text-green-400' : 'text-red-400'
                }`}>
                  {status?.status.toUpperCase()}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-navy-300">Last Update</div>
              <div className="text-white font-mono">{new Date().toLocaleTimeString()}</div>
            </div>
          </div>
        </div>

        {/* Quick Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            icon="💬"
            label="Total Messages"
            value={metrics?.messages.total.toLocaleString() || '0'}
            subtext={`${metrics?.messages.last_24h || 0} in last 24h`}
            color="from-blue-600 to-blue-800"
          />
          <StatCard
            icon="📚"
            label="Conversations"
            value={status?.database.conversations.toLocaleString() || '0'}
            subtext="Active sessions"
            color="from-purple-600 to-purple-800"
          />
          <StatCard
            icon="🔥"
            label="Token Usage"
            value={((metrics?.messages.total_tokens || 0) / 1000000).toFixed(2) + 'M'}
            subtext="Tokens processed"
            color="from-orange-600 to-orange-800"
          />
          <StatCard
            icon="🛡️"
            label="Security Events"
            value={metrics?.security.security_alerts || '0'}
            subtext="Alerts detected"
            color="from-red-600 to-red-800"
          />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Security Score */}
          <div className="lg:col-span-1">
            <SecurityScore />
          </div>

          {/* System Resources */}
          <div className="lg:col-span-2">
            <div className="bg-navy-950 rounded-lg border border-navy-800 p-6 relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-transparent to-transparent pointer-events-none" />
              <div className="relative z-10">
                <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                  <span className="text-2xl">⚡</span>
                  System Resources
                </h3>

                <div className="space-y-6">
                  <ResourceBar
                    label="CPU Usage"
                    icon="⚙️"
                    value={status?.resources.cpu_percent || 0}
                    max={100}
                    unit="%"
                  />
                  <ResourceBar
                    label="Memory Usage"
                    icon="💾"
                    value={status?.resources.memory_percent || 0}
                    max={100}
                    unit="%"
                    subtitle={`${status?.resources.memory_available_gb.toFixed(2)} GB available`}
                  />
                  <ResourceBar
                    label="Disk Usage"
                    icon="💿"
                    value={status?.resources.disk_percent || 0}
                    max={100}
                    unit="%"
                    subtitle={`${status?.resources.disk_free_gb.toFixed(2)} GB free`}
                  />
                </div>

                {/* Component Status */}
                <div className="mt-6 pt-6 border-t border-navy-800">
                  <div className="text-sm font-semibold text-navy-300 mb-3">Core Components</div>
                  <div className="grid grid-cols-3 gap-3">
                    <ComponentBadge
                      name="Claude AI"
                      status={status?.components.claude_api || 'unknown'}
                      icon="🤖"
                    />
                    <ComponentBadge
                      name="Security"
                      status={status?.components.security_layer || 'unknown'}
                      icon="🛡️"
                    />
                    <ComponentBadge
                      name="Memory"
                      status={status?.components.memory_manager || 'unknown'}
                      icon="🧠"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Kanban Board */}
        <div className="mb-8">
          <KanbanBoard />
        </div>

        {/* Database Stats */}
        <div className="bg-navy-950 rounded-lg border border-navy-800 p-6 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-900/10 to-transparent pointer-events-none" />
          <div className="relative z-10">
            <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
              <span className="text-2xl">🗄️</span>
              Database Statistics
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <DatabaseStat
                label="Messages"
                value={status?.database.messages.toLocaleString()}
                icon="💬"
                subtitle={`${metrics?.messages.total_tokens.toLocaleString()} tokens`}
              />
              <DatabaseStat
                label="Conversations"
                value={status?.database.conversations.toLocaleString()}
                icon="📚"
              />
              <DatabaseStat
                label="Audit Logs"
                value={status?.database.audit_logs.toLocaleString()}
                icon="📋"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, subtext, color }: {
  icon: string
  label: string
  value: string
  subtext: string
  color: string
}) {
  return (
    <div className="bg-navy-950 rounded-lg border border-navy-800 p-6 relative overflow-hidden group hover:border-navy-600 transition-all">
      <div className={`absolute inset-0 bg-gradient-to-br ${color} opacity-10 group-hover:opacity-20 transition-opacity`} />
      <div className="relative z-10">
        <div className="text-4xl mb-3">{icon}</div>
        <div className="text-sm text-navy-300 mb-1">{label}</div>
        <div className="text-3xl font-bold text-white mb-1">{value}</div>
        <div className="text-xs text-navy-400">{subtext}</div>
      </div>
    </div>
  )
}

function ResourceBar({ label, icon, value, max, unit, subtitle }: {
  label: string
  icon: string
  value: number
  max: number
  unit: string
  subtitle?: string
}) {
  const percentage = (value / max) * 100
  const getColor = () => {
    if (percentage < 50) return 'from-green-500 to-green-600'
    if (percentage < 80) return 'from-yellow-500 to-yellow-600'
    return 'from-red-500 to-red-600'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">{icon}</span>
          <span className="text-sm font-semibold text-white">{label}</span>
        </div>
        <span className="text-sm text-navy-300">{value.toFixed(1)}{unit}</span>
      </div>
      <div className="w-full bg-navy-900 rounded-full h-3 overflow-hidden border border-navy-800">
        <div
          className={`h-full bg-gradient-to-r ${getColor()} transition-all duration-500 relative`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        >
          <div className="absolute inset-0 bg-white/20 animate-pulse-slow" />
        </div>
      </div>
      {subtitle && (
        <div className="text-xs text-navy-400 mt-1">{subtitle}</div>
      )}
    </div>
  )
}

function ComponentBadge({ name, status, icon }: { name: string; status: string; icon: string }) {
  const isOperational = status === 'operational'

  return (
    <div className={`text-center p-3 rounded-lg border ${
      isOperational
        ? 'border-green-500/50 bg-green-900/20'
        : 'border-red-500/50 bg-red-900/20'
    }`}>
      <div className="text-2xl mb-1">{icon}</div>
      <div className="text-xs font-semibold text-white">{name}</div>
      <div className={`text-xs ${isOperational ? 'text-green-400' : 'text-red-400'}`}>
        {isOperational ? 'Online' : 'Offline'}
      </div>
    </div>
  )
}

function DatabaseStat({ label, value, icon, subtitle }: {
  label: string
  value?: string
  icon: string
  subtitle?: string
}) {
  return (
    <div className="text-center">
      <div className="text-4xl mb-2">{icon}</div>
      <div className="text-sm text-navy-300 mb-1">{label}</div>
      <div className="text-3xl font-bold text-white">{value || '0'}</div>
      {subtitle && (
        <div className="text-xs text-navy-400 mt-1">{subtitle}</div>
      )}
    </div>
  )
}
