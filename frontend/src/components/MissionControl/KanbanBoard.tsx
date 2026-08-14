import { useState } from 'react'

interface Task {
  id: string
  title: string
  description?: string
  status: 'backlog' | 'in_progress' | 'blocked' | 'complete'
  priority?: 'low' | 'medium' | 'high'
}

export default function KanbanBoard() {
  const [tasks, setTasks] = useState<Task[]>([
    { id: '1', title: 'Phase 1: Core System', status: 'complete', priority: 'high' },
    { id: '2', title: 'Phase 2: Mission Control', status: 'complete', priority: 'high' },
    { id: '3', title: 'Phase 3: Automation Engine', status: 'in_progress', priority: 'high' },
    { id: '4', title: 'Content Trend Scanner', status: 'backlog', priority: 'medium' },
    { id: '5', title: 'Government Intel Scanner', status: 'backlog', priority: 'medium' },
    { id: '6', title: 'Google Sheets Integration', status: 'backlog', priority: 'low' },
  ])

  const columns = [
    { id: 'backlog', title: 'Backlog', icon: '📋', color: 'from-gray-700 to-gray-800' },
    { id: 'in_progress', title: 'In Progress', icon: '⚙️', color: 'from-blue-700 to-blue-800' },
    { id: 'blocked', title: 'Blocked', icon: '🚧', color: 'from-red-700 to-red-800' },
    { id: 'complete', title: 'Complete', icon: '✅', color: 'from-green-700 to-green-800' },
  ]

  const getTasksByStatus = (status: string) => {
    return tasks.filter(task => task.status === status)
  }

  const getPriorityColor = (priority?: string) => {
    switch (priority) {
      case 'high': return 'border-red-500 bg-red-500/10'
      case 'medium': return 'border-yellow-500 bg-yellow-500/10'
      case 'low': return 'border-blue-500 bg-blue-500/10'
      default: return 'border-gray-600 bg-gray-800'
    }
  }

  return (
    <div className="bg-navy-950 rounded-lg border border-navy-800 p-6 relative overflow-hidden">
      {/* Glowing gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-navy-900/50 via-transparent to-blue-900/20 pointer-events-none" />

      <div className="relative z-10">
        <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
          <span className="text-2xl">📊</span>
          Project Kanban Board
        </h3>

        {/* Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          {columns.map((column) => (
            <div key={column.id} className="flex flex-col">
              {/* Column Header */}
              <div className={`bg-gradient-to-r ${column.color} rounded-t-lg p-3 border border-navy-700`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{column.icon}</span>
                    <span className="font-semibold text-white text-sm">{column.title}</span>
                  </div>
                  <div className="bg-white/20 rounded-full px-2 py-0.5 text-xs font-bold text-white">
                    {getTasksByStatus(column.id).length}
                  </div>
                </div>
              </div>

              {/* Column Body */}
              <div className="bg-navy-900/50 border-x border-b border-navy-700 rounded-b-lg p-3 min-h-[300px] space-y-2">
                {getTasksByStatus(column.id).map((task) => (
                  <div
                    key={task.id}
                    className={`p-3 rounded-lg border-l-4 ${getPriorityColor(task.priority)} backdrop-blur-sm cursor-pointer hover:scale-105 transition-transform`}
                  >
                    <div className="text-sm font-semibold text-white mb-1">{task.title}</div>
                    {task.description && (
                      <div className="text-xs text-gray-400">{task.description}</div>
                    )}
                    {task.priority && (
                      <div className="mt-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          task.priority === 'high' ? 'bg-red-500 text-white' :
                          task.priority === 'medium' ? 'bg-yellow-500 text-black' :
                          'bg-blue-500 text-white'
                        }`}>
                          {task.priority.toUpperCase()}
                        </span>
                      </div>
                    )}
                  </div>
                ))}

                {getTasksByStatus(column.id).length === 0 && (
                  <div className="text-center text-gray-600 text-sm py-8">
                    No tasks
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Stats */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-navy-900/50 rounded-lg p-3 border border-navy-800 text-center">
            <div className="text-2xl font-bold text-white">{tasks.length}</div>
            <div className="text-xs text-gray-400">Total Tasks</div>
          </div>
          <div className="bg-navy-900/50 rounded-lg p-3 border border-navy-800 text-center">
            <div className="text-2xl font-bold text-blue-400">{getTasksByStatus('in_progress').length}</div>
            <div className="text-xs text-gray-400">Active</div>
          </div>
          <div className="bg-navy-900/50 rounded-lg p-3 border border-navy-800 text-center">
            <div className="text-2xl font-bold text-green-400">{getTasksByStatus('complete').length}</div>
            <div className="text-xs text-gray-400">Completed</div>
          </div>
          <div className="bg-navy-900/50 rounded-lg p-3 border border-navy-800 text-center">
            <div className="text-2xl font-bold text-white">
              {Math.round((getTasksByStatus('complete').length / tasks.length) * 100)}%
            </div>
            <div className="text-xs text-gray-400">Progress</div>
          </div>
        </div>
      </div>
    </div>
  )
}
