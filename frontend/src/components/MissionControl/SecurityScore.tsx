import { useState, useEffect } from 'react'
import { systemApi } from '../../services/api'
import type { AuditLog } from '../../types'

export default function SecurityScore() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [score, setScore] = useState(100)
  const [issues, setIssues] = useState<AuditLog[]>([])

  useEffect(() => {
    fetchSecurityData()
    const interval = setInterval(fetchSecurityData, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchSecurityData = async () => {
    try {
      const data = await systemApi.getLogs(100)
      setLogs(data)

      // Calculate security score
      const warnings = data.filter(l => l.severity === 'warning').length
      const errors = data.filter(l => l.severity === 'error').length
      const critical = data.filter(l => l.severity === 'critical').length

      // Score calculation (start at 100, deduct points)
      let calculatedScore = 100
      calculatedScore -= warnings * 2
      calculatedScore -= errors * 5
      calculatedScore -= critical * 15
      calculatedScore = Math.max(0, Math.min(100, calculatedScore))

      setScore(calculatedScore)

      // Get recent security issues
      const securityIssues = data.filter(l =>
        l.severity === 'warning' || l.severity === 'error' || l.severity === 'critical'
      ).slice(0, 5)

      setIssues(securityIssues)
    } catch (error) {
      console.error('Failed to fetch security data:', error)
    }
  }

  const getScoreColor = () => {
    if (score >= 90) return { bg: 'bg-green-500', text: 'text-green-400', glow: 'shadow-green-500/50' }
    if (score >= 70) return { bg: 'bg-yellow-500', text: 'text-yellow-400', glow: 'shadow-yellow-500/50' }
    return { bg: 'bg-red-500', text: 'text-red-400', glow: 'shadow-red-500/50' }
  }

  const getScoreLabel = () => {
    if (score >= 90) return 'EXCELLENT'
    if (score >= 70) return 'GOOD'
    if (score >= 50) return 'FAIR'
    return 'CRITICAL'
  }

  const colors = getScoreColor()

  return (
    <div className="bg-navy-950 rounded-lg border border-navy-800 p-6 relative overflow-hidden">
      {/* Glowing effect */}
      <div className={`absolute inset-0 ${colors.bg} opacity-5 blur-3xl`} />

      <div className="relative z-10">
        <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
          <span className="text-2xl">🛡️</span>
          Security Score
        </h3>

        {/* Score Circle */}
        <div className="flex items-center justify-center mb-6">
          <div className="relative">
            {/* Outer glow ring */}
            <div className={`absolute inset-0 rounded-full ${colors.bg} opacity-20 blur-xl animate-pulse-slow`} />

            {/* Score circle */}
            <div className={`relative w-32 h-32 rounded-full border-4 ${colors.bg} flex items-center justify-center shadow-lg ${colors.glow}`}>
              <div className="text-center">
                <div className={`text-4xl font-bold ${colors.text}`}>{score}</div>
                <div className="text-xs text-gray-400">/ 100</div>
              </div>
            </div>
          </div>
        </div>

        {/* Status Label */}
        <div className="text-center mb-6">
          <div className={`inline-block px-4 py-2 rounded-full ${colors.bg} bg-opacity-20 border border-current ${colors.text}`}>
            <span className="font-semibold">{getScoreLabel()}</span>
          </div>
        </div>

        {/* Security Stats */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-yellow-400">
              {logs.filter(l => l.severity === 'warning').length}
            </div>
            <div className="text-xs text-gray-400">Warnings</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-400">
              {logs.filter(l => l.severity === 'error').length}
            </div>
            <div className="text-xs text-gray-400">Errors</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-500">
              {logs.filter(l => l.severity === 'critical').length}
            </div>
            <div className="text-xs text-gray-400">Critical</div>
          </div>
        </div>

        {/* Outstanding Issues */}
        {issues.length > 0 && (
          <div>
            <div className="text-sm font-semibold text-gray-400 mb-2">Outstanding Issues</div>
            <div className="space-y-2 max-h-40 overflow-y-auto scrollbar-thin">
              {issues.map((issue, idx) => (
                <div
                  key={idx}
                  className="text-xs bg-navy-900 rounded px-3 py-2 border border-navy-800"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      issue.severity === 'critical' ? 'bg-red-500 text-white' :
                      issue.severity === 'error' ? 'bg-red-400 text-white' :
                      'bg-yellow-400 text-black'
                    }`}>
                      {issue.severity.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-gray-300">{issue.description}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {issues.length === 0 && (
          <div className="text-center text-sm text-green-400">
            ✓ No outstanding security issues
          </div>
        )}
      </div>
    </div>
  )
}
