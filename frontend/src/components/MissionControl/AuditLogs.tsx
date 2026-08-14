import { useState, useEffect } from 'react'
import { systemApi } from '../../services/api'
import type { AuditLog } from '../../types'
import { formatDistanceToNow } from 'date-fns'

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('all')

  const fetchLogs = async () => {
    try {
      const data = await systemApi.getLogs(100)
      setLogs(data)
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch logs:', error)
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchLogs, 30000)
    return () => clearInterval(interval)
  }, [])

  const filteredLogs = filter === 'all'
    ? logs
    : logs.filter(log => log.severity === filter)

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'info': return 'text-blue-400 bg-blue-900/30 border-blue-600'
      case 'warning': return 'text-yellow-400 bg-yellow-900/30 border-yellow-600'
      case 'error': return 'text-red-400 bg-red-900/30 border-red-600'
      case 'critical': return 'text-red-500 bg-red-900/50 border-red-500'
      default: return 'text-navy-400 bg-navy-900/30 border-navy-700'
    }
  }

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'info': return 'ℹ️'
      case 'warning': return '⚠️'
      case 'error': return '❌'
      case 'critical': return '🚨'
      default: return '📋'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-navy-950">
        <div className="text-center">
          <div className="text-4xl mb-4 animate-pulse">📋</div>
          <div className="text-navy-300 animate-pulse">Loading audit logs...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-8 bg-navy-950">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3">
            <span className="text-4xl animate-pulse">📋</span>
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">Security Audit Logs</h1>
              <p className="text-navy-300">System events and security monitoring</p>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-6 flex gap-3 flex-wrap">
          <button
            onClick={() => setFilter('all')}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === 'all'
                ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-500/50'
                : 'bg-navy-900 text-navy-300 hover:bg-navy-800 hover:text-white border border-navy-800'
            }`}
          >
            All Logs
          </button>
          <button
            onClick={() => setFilter('info')}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === 'info'
                ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-500/50'
                : 'bg-navy-900 text-navy-300 hover:bg-navy-800 hover:text-white border border-navy-800'
            }`}
          >
            Info
          </button>
          <button
            onClick={() => setFilter('warning')}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === 'warning'
                ? 'bg-gradient-to-r from-yellow-600 to-yellow-700 text-white shadow-lg shadow-yellow-500/50'
                : 'bg-navy-900 text-navy-300 hover:bg-navy-800 hover:text-white border border-navy-800'
            }`}
          >
            Warnings
          </button>
          <button
            onClick={() => setFilter('error')}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === 'error'
                ? 'bg-gradient-to-r from-red-600 to-red-700 text-white shadow-lg shadow-red-500/50'
                : 'bg-navy-900 text-navy-300 hover:bg-navy-800 hover:text-white border border-navy-800'
            }`}
          >
            Errors
          </button>
          <button
            onClick={() => setFilter('critical')}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === 'critical'
                ? 'bg-gradient-to-r from-red-700 to-red-800 text-white shadow-lg shadow-red-500/50'
                : 'bg-navy-900 text-navy-300 hover:bg-navy-800 hover:text-white border border-navy-800'
            }`}
          >
            Critical
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-navy-950 rounded-lg p-4 border border-navy-800 relative overflow-hidden group hover:border-navy-600 transition-all">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-transparent to-transparent pointer-events-none" />
            <div className="relative z-10">
              <div className="text-sm text-navy-300 mb-1">Total Events</div>
              <div className="text-2xl font-bold text-white">{logs.length}</div>
            </div>
          </div>
          <div className="bg-navy-950 rounded-lg p-4 border border-navy-800 relative overflow-hidden group hover:border-navy-600 transition-all">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 via-transparent to-transparent pointer-events-none" />
            <div className="relative z-10">
              <div className="text-sm text-navy-300 mb-1">Info</div>
              <div className="text-2xl font-bold text-blue-400">
                {logs.filter(l => l.severity === 'info').length}
              </div>
            </div>
          </div>
          <div className="bg-navy-950 rounded-lg p-4 border border-navy-800 relative overflow-hidden group hover:border-navy-600 transition-all">
            <div className="absolute inset-0 bg-gradient-to-br from-yellow-600/20 via-transparent to-transparent pointer-events-none" />
            <div className="relative z-10">
              <div className="text-sm text-navy-300 mb-1">Warnings</div>
              <div className="text-2xl font-bold text-yellow-400">
                {logs.filter(l => l.severity === 'warning').length}
              </div>
            </div>
          </div>
          <div className="bg-navy-950 rounded-lg p-4 border border-navy-800 relative overflow-hidden group hover:border-navy-600 transition-all">
            <div className="absolute inset-0 bg-gradient-to-br from-red-600/20 via-transparent to-transparent pointer-events-none" />
            <div className="relative z-10">
              <div className="text-sm text-navy-300 mb-1">Errors</div>
              <div className="text-2xl font-bold text-red-400">
                {logs.filter(l => l.severity === 'error' || l.severity === 'critical').length}
              </div>
            </div>
          </div>
        </div>

        {/* Logs List */}
        <div className="space-y-3">
          {filteredLogs.map((log) => (
            <div
              key={log.id}
              className={`bg-navy-900/50 backdrop-blur-sm rounded-lg p-4 border ${getSeverityColor(log.severity)} hover:scale-[1.01] transition-transform`}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{getSeverityIcon(log.severity)}</span>
                  <div>
                    <div className="font-semibold text-white">{log.event_type.replace(/_/g, ' ').toUpperCase()}</div>
                    <div className="text-sm text-navy-300">
                      {log.user_id && `User: ${log.user_id}`}
                    </div>
                  </div>
                </div>
                <div className="text-xs text-navy-400 font-mono">
                  {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                </div>
              </div>
              <div className="text-sm text-navy-100 mb-2">{log.description}</div>
              {log.metadata && Object.keys(log.metadata).length > 0 && (
                <div className="text-xs text-navy-300 bg-navy-950 rounded px-3 py-2 font-mono border border-navy-800">
                  {JSON.stringify(log.metadata, null, 2)}
                </div>
              )}
            </div>
          ))}

          {filteredLogs.length === 0 && (
            <div className="text-center py-12">
              <div className="text-4xl mb-4">🔍</div>
              <div className="text-navy-400">No logs found for the selected filter</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
