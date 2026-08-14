import { useState, useEffect } from 'react'
import { systemApi } from '../../services/api'
import type { SystemStatus } from '../../types'

export default function SystemHealth() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())

  const fetchStatus = async () => {
    try {
      const data = await systemApi.getStatus()
      setStatus(data)
      setLastUpdate(new Date())
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch status:', error)
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    // Auto-refresh every 5 seconds
    const interval = setInterval(fetchStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-navy-950">
        <div className="text-center">
          <div className="text-4xl mb-4 animate-pulse">🏥</div>
          <div className="text-navy-300 animate-pulse">Loading system health...</div>
        </div>
      </div>
    )
  }

  const isHealthy = status?.status === 'operational'

  return (
    <div className="h-full overflow-y-auto p-8 bg-navy-950">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-4xl animate-pulse">🏥</span>
              <div>
                <h1 className="text-3xl font-bold text-white mb-2">System Health Monitor</h1>
                <p className="text-navy-300">Real-time system monitoring and diagnostics</p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-navy-400 mb-1">Last Updated</div>
              <div className="text-sm text-white font-mono">{lastUpdate.toLocaleTimeString()}</div>
            </div>
          </div>
        </div>

        {/* Overall Status */}
        <div className={`rounded-lg p-8 mb-8 border-2 relative overflow-hidden ${
          isHealthy
            ? 'bg-gradient-to-r from-green-900/20 to-green-800/10 border-green-500'
            : 'bg-gradient-to-r from-red-900/20 to-red-800/10 border-red-500'
        }`}>
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-pulse-slow" />
          <div className="relative z-10 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`relative h-16 w-16 rounded-full flex items-center justify-center text-4xl ${
                isHealthy ? 'bg-green-500' : 'bg-red-500'
              } shadow-lg ${isHealthy ? 'shadow-green-500/50' : 'shadow-red-500/50'}`}>
                <div className={`absolute inset-0 rounded-full ${isHealthy ? 'bg-green-500' : 'bg-red-500'} opacity-20 blur-xl animate-pulse-slow`} />
                <span className="relative z-10">{isHealthy ? '✓' : '✗'}</span>
              </div>
              <div>
                <div className="text-sm text-navy-300 mb-1">Overall System Status</div>
                <div className={`text-3xl font-bold ${
                  isHealthy ? 'text-green-400' : 'text-red-400'
                }`}>
                  {status?.status.toUpperCase()}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Components Health */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">⚙️</span>
            Core Components
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ComponentCard
              name="Claude API"
              status={status?.components.claude_api || 'unknown'}
              description="AI inference engine"
              icon="🤖"
            />
            <ComponentCard
              name="Security Layer"
              status={status?.components.security_layer || 'unknown'}
              description="Threat protection"
              icon="🛡️"
            />
            <ComponentCard
              name="Memory Manager"
              status={status?.components.memory_manager || 'unknown'}
              description="Conversation context"
              icon="🧠"
            />
          </div>
        </div>

        {/* Resource Monitoring */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">📊</span>
            Resource Utilization
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <ResourceCard
              title="CPU"
              value={status?.resources.cpu_percent || 0}
              unit="%"
              icon="⚙️"
              thresholds={{ warning: 70, critical: 90 }}
            />
            <ResourceCard
              title="Memory"
              value={status?.resources.memory_percent || 0}
              unit="%"
              icon="💾"
              thresholds={{ warning: 70, critical: 90 }}
              subtitle={`${status?.resources.memory_available_gb.toFixed(2)} GB available`}
            />
            <ResourceCard
              title="Disk"
              value={status?.resources.disk_percent || 0}
              unit="%"
              icon="💿"
              thresholds={{ warning: 80, critical: 95 }}
              subtitle={`${status?.resources.disk_free_gb.toFixed(2)} GB free`}
            />
            <div className="bg-navy-950 rounded-lg p-6 border border-navy-800 relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-transparent to-transparent pointer-events-none" />
              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-3xl">🔗</span>
                  <div>
                    <div className="text-sm text-navy-300">Database</div>
                    <div className="text-xl font-bold text-white">Connected</div>
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-navy-300">Conversations</span>
                    <span className="text-white font-semibold">{status?.database.conversations.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-navy-300">Messages</span>
                    <span className="text-white font-semibold">{status?.database.messages.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-navy-300">Audit Logs</span>
                    <span className="text-white font-semibold">{status?.database.audit_logs.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Health Checklist */}
        <div>
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">✅</span>
            Health Checklist
          </h2>
          <div className="bg-navy-950 rounded-lg p-6 border border-navy-800 relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-green-900/10 via-transparent to-transparent pointer-events-none" />
            <div className="relative z-10">
            <div className="space-y-3">
              <ChecklistItem
                label="System operational"
                status={status?.status === 'operational'}
              />
              <ChecklistItem
                label="All components online"
                status={
                  status?.components.claude_api === 'operational' &&
                  status?.components.security_layer === 'operational' &&
                  status?.components.memory_manager === 'operational'
                }
              />
              <ChecklistItem
                label="CPU usage normal"
                status={(status?.resources.cpu_percent || 0) < 80}
              />
              <ChecklistItem
                label="Memory available"
                status={(status?.resources.memory_percent || 0) < 80}
              />
              <ChecklistItem
                label="Disk space sufficient"
                status={(status?.resources.disk_percent || 0) < 90}
              />
            </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ComponentCard({ name, status, description, icon }: {
  name: string
  status: string
  description: string
  icon: string
}) {
  const isOperational = status === 'operational'

  return (
    <div className={`bg-navy-950 rounded-lg p-6 border relative overflow-hidden group hover:border-navy-600 transition-all ${
      isOperational ? 'border-green-800' : 'border-red-800'
    }`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${
        isOperational ? 'from-green-900/20' : 'from-red-900/20'
      } via-transparent to-transparent pointer-events-none`} />
      <div className="relative z-10">
        <div className="flex items-start justify-between mb-3">
          <span className="text-3xl">{icon}</span>
          <div className={`h-3 w-3 rounded-full ${
            isOperational ? 'bg-green-500 animate-pulse' : 'bg-red-500 animate-pulse'
          }`} />
        </div>
        <div className="text-lg font-semibold text-white mb-1">{name}</div>
        <div className="text-sm text-navy-300 mb-3">{description}</div>
        <div className={`text-sm font-medium ${
          isOperational ? 'text-green-400' : 'text-red-400'
        }`}>
          {status}
        </div>
      </div>
    </div>
  )
}

function ResourceCard({ title, value, unit, icon, thresholds, subtitle }: {
  title: string
  value: number
  unit: string
  icon: string
  thresholds: { warning: number; critical: number }
  subtitle?: string
}) {
  const getStatus = () => {
    if (value >= thresholds.critical) return { color: 'red', label: 'Critical' }
    if (value >= thresholds.warning) return { color: 'yellow', label: 'Warning' }
    return { color: 'green', label: 'Normal' }
  }

  const status = getStatus()
  const getColor = () => {
    if (value >= thresholds.critical) return 'from-red-500 to-red-600'
    if (value >= thresholds.warning) return 'from-yellow-500 to-yellow-600'
    return 'from-green-500 to-green-600'
  }

  return (
    <div className="bg-navy-950 rounded-lg p-6 border border-navy-800 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-transparent to-transparent pointer-events-none" />
      <div className="relative z-10">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-3xl">{icon}</span>
          <div>
            <div className="text-sm text-navy-300">{title}</div>
            <div className="text-2xl font-bold text-white">{value.toFixed(1)}{unit}</div>
          </div>
        </div>
        <div className="w-full bg-navy-900 rounded-full h-3 mb-3 overflow-hidden border border-navy-800">
          <div
            className={`h-3 bg-gradient-to-r ${getColor()} transition-all duration-500 relative`}
            style={{ width: `${Math.min(value, 100)}%` }}
          >
            <div className="absolute inset-0 bg-white/20 animate-pulse-slow" />
          </div>
        </div>
        <div className="flex justify-between items-center text-sm">
          <span className={`font-medium ${
            status.color === 'red' ? 'text-red-400' :
            status.color === 'yellow' ? 'text-yellow-400' :
            'text-green-400'
          }`}>{status.label}</span>
          {subtitle && <span className="text-navy-400">{subtitle}</span>}
        </div>
      </div>
    </div>
  )
}

function ChecklistItem({ label, status }: { label: string; status: boolean }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-navy-200">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`text-sm ${status ? 'text-green-400' : 'text-red-400'}`}>
          {status ? 'Pass' : 'Fail'}
        </span>
        <div className={`h-5 w-5 rounded-full flex items-center justify-center ${
          status ? 'bg-green-500' : 'bg-red-500'
        }`}>
          <span className="text-white text-xs">{status ? '✓' : '✗'}</span>
        </div>
      </div>
    </div>
  )
}
