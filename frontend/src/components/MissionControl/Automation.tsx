import { useState, useEffect } from 'react'
import { automationApi } from '../../services/api'

interface AutomationJob {
  id: string
  name: string
  next_run: string | null
  trigger: string
}

interface AutomationStatus {
  success: boolean
  scheduler_running: boolean
  jobs_scheduled: number
  timezone: string
  jobs: AutomationJob[]
}

export default function Automation() {
  const [status, setStatus] = useState<AutomationStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())

  const fetchStatus = async () => {
    try {
      const data = await automationApi.getStatus()
      setStatus(data)
      setLastUpdate(new Date())
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch automation status:', error)
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [])

  const handleTriggerJob = async (jobId: string, jobName: string) => {
    if (!confirm(`Manually trigger "${jobName}"?\n\nThis will run the automation task immediately.`)) {
      return
    }

    setTriggering(jobId)
    try {
      const result = await automationApi.triggerJob(jobId)
      alert(`✓ ${jobName} triggered successfully!\n\nCheck your Google Sheets for results.`)
      console.log('Trigger result:', result)
      fetchStatus() // Refresh status
    } catch (error) {
      console.error('Failed to trigger job:', error)
      alert(`✗ Failed to trigger ${jobName}\n\nCheck console for details.`)
    } finally {
      setTriggering(null)
    }
  }

  const formatNextRun = (nextRun: string | null) => {
    if (!nextRun) return 'Not scheduled'

    const date = new Date(nextRun)
    const now = new Date()
    const diff = date.getTime() - now.getTime()
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

    if (diff < 0) return 'Overdue'
    if (hours < 1) return `In ${minutes} minutes`
    if (hours < 24) return `In ${hours} hours, ${minutes} minutes`

    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    })
  }

  const getJobIcon = (jobId: string) => {
    if (jobId === 'content_trend_scanner') return '📊'
    if (jobId === 'government_intel_scanner') return '🏛️'
    return '⚙️'
  }

  const getJobDescription = (jobId: string) => {
    if (jobId === 'content_trend_scanner') {
      return 'Scans X, Instagram, LinkedIn, TikTok for trending content. Writes top 10 to Google Sheets.'
    }
    if (jobId === 'government_intel_scanner') {
      return 'Fetches updates from Federal Reserve, FDIC, OCC, CFPB. Writes top 20 to Google Sheets.'
    }
    return 'Automation task'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-navy-950">
        <div className="text-center">
          <div className="text-4xl mb-4 animate-pulse">⚙️</div>
          <div className="text-navy-300 animate-pulse">Loading automation status...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-8 bg-navy-950">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-4xl animate-pulse">⚙️</span>
              <div>
                <h1 className="text-3xl font-bold text-white mb-2">Automation Engine</h1>
                <p className="text-navy-300">Daily intelligence gathering and report generation</p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-navy-400 mb-1">Last Updated</div>
              <div className="text-sm text-white font-mono">{lastUpdate.toLocaleTimeString()}</div>
            </div>
          </div>
        </div>

        {/* Status Banner */}
        <div className={`mb-8 rounded-lg border-2 p-6 relative overflow-hidden ${
          status?.scheduler_running
            ? 'border-green-500 bg-gradient-to-r from-green-900/20 to-green-800/10'
            : 'border-red-500 bg-gradient-to-r from-red-900/20 to-red-800/10'
        }`}>
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-pulse-slow" />
          <div className="relative z-10 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`h-4 w-4 rounded-full ${
                status?.scheduler_running ? 'bg-green-500 animate-pulse' : 'bg-red-500 animate-pulse'
              }`} />
              <div>
                <div className="text-sm text-navy-300">Scheduler Status</div>
                <div className={`text-2xl font-bold ${
                  status?.scheduler_running ? 'text-green-400' : 'text-red-400'
                }`}>
                  {status?.scheduler_running ? 'RUNNING' : 'STOPPED'}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-navy-300">Timezone</div>
              <div className="text-white font-mono">{status?.timezone || 'America/Los_Angeles'}</div>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-navy-950 rounded-lg border border-navy-800 p-6 relative overflow-hidden group hover:border-navy-600 transition-all">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-transparent to-transparent pointer-events-none" />
            <div className="relative z-10">
              <div className="text-4xl mb-3">📅</div>
              <div className="text-sm text-navy-300 mb-1">Scheduled Tasks</div>
              <div className="text-3xl font-bold text-white">{status?.jobs_scheduled || 0}</div>
            </div>
          </div>

          <div className="bg-navy-950 rounded-lg border border-navy-800 p-6 relative overflow-hidden group hover:border-navy-600 transition-all">
            <div className="absolute inset-0 bg-gradient-to-br from-green-900/20 via-transparent to-transparent pointer-events-none" />
            <div className="relative z-10">
              <div className="text-4xl mb-3">⏰</div>
              <div className="text-sm text-navy-300 mb-1">Daily Schedule</div>
              <div className="text-lg font-bold text-white">7:00 AM & 8:00 AM</div>
              <div className="text-xs text-navy-400">PST/PDT</div>
            </div>
          </div>

          <div className="bg-navy-950 rounded-lg border border-navy-800 p-6 relative overflow-hidden group hover:border-navy-600 transition-all">
            <div className="absolute inset-0 bg-gradient-to-br from-purple-900/20 via-transparent to-transparent pointer-events-none" />
            <div className="relative z-10">
              <div className="text-4xl mb-3">📊</div>
              <div className="text-sm text-navy-300 mb-1">Output</div>
              <div className="text-lg font-bold text-white">Google Sheets</div>
              <div className="text-xs text-navy-400">2 sheets updated daily</div>
            </div>
          </div>
        </div>

        {/* Scheduled Jobs */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-2xl">📋</span>
            Scheduled Automation Tasks
          </h2>

          <div className="space-y-4">
            {status?.jobs.map((job) => (
              <div
                key={job.id}
                className="bg-navy-950 rounded-lg border border-navy-800 p-6 relative overflow-hidden hover:border-navy-600 transition-all"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-blue-900/10 via-transparent to-transparent pointer-events-none" />
                <div className="relative z-10">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-start gap-4 flex-1">
                      <span className="text-4xl">{getJobIcon(job.id)}</span>
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-white mb-2">{job.name}</h3>
                        <p className="text-sm text-navy-300 mb-3">{getJobDescription(job.id)}</p>

                        <div className="flex items-center gap-6 text-sm">
                          <div>
                            <span className="text-navy-400">Schedule:</span>
                            <span className="text-white ml-2 font-mono">{job.trigger}</span>
                          </div>
                          <div>
                            <span className="text-navy-400">Next Run:</span>
                            <span className="text-green-400 ml-2 font-semibold">{formatNextRun(job.next_run)}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => handleTriggerJob(job.id, job.name)}
                      disabled={triggering === job.id}
                      className="px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-navy-800 disabled:to-navy-800 disabled:cursor-not-allowed rounded-lg font-semibold transition-all shadow-lg shadow-blue-500/30 disabled:shadow-none text-sm"
                    >
                      {triggering === job.id ? 'Running...' : 'Run Now'}
                    </button>
                  </div>
                </div>
              </div>
            ))}

            {(!status?.jobs || status.jobs.length === 0) && (
              <div className="text-center py-12">
                <div className="text-4xl mb-4">📭</div>
                <div className="text-navy-400">No scheduled tasks found</div>
              </div>
            )}
          </div>
        </div>

        {/* Google Sheets Links */}
        <div className="bg-navy-950 rounded-lg border border-navy-800 p-6 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-green-900/10 via-transparent to-transparent pointer-events-none" />
          <div className="relative z-10">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <span className="text-2xl">📊</span>
              Daily Report Sheets
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <a
                href="https://docs.google.com/spreadsheets/d/1yGYSpeD8AjHYtZLqJ0nVVAb7KOKm1EwDq1VJJLROxFw"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-4 bg-navy-900/50 rounded-lg border border-navy-800 hover:border-blue-500 transition-all group"
              >
                <span className="text-3xl">📈</span>
                <div className="flex-1">
                  <div className="font-semibold text-white group-hover:text-blue-400 transition-colors">
                    Content Trends
                  </div>
                  <div className="text-xs text-navy-400">Daily Trending Intelligence</div>
                </div>
                <span className="text-navy-400 group-hover:text-blue-400 transition-colors">→</span>
              </a>

              <a
                href="https://docs.google.com/spreadsheets/d/1pHSIlyFwAEIHEs4L15S_i1nTsCRX58ISNNyH0Xw_7Fo"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-4 bg-navy-900/50 rounded-lg border border-navy-800 hover:border-green-500 transition-all group"
              >
                <span className="text-3xl">🏛️</span>
                <div className="flex-1">
                  <div className="font-semibold text-white group-hover:text-green-400 transition-colors">
                    Government Intel
                  </div>
                  <div className="text-xs text-navy-400">Banking Intelligence</div>
                </div>
                <span className="text-navy-400 group-hover:text-green-400 transition-colors">→</span>
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
