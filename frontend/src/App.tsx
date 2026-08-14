import { useState } from 'react'
import Dashboard from './components/MissionControl/Dashboard'
import ChatInterface from './components/Chat/ChatInterface'
import AuditLogs from './components/MissionControl/AuditLogs'
import SystemHealth from './components/MissionControl/SystemHealth'
import Automation from './components/MissionControl/Automation'
import ManusDashboard from './components/MissionControl/ManusDashboard'
import Starfield from './components/Starfield'
import ShootingStars from './components/ShootingStars'

type View = 'dashboard' | 'automation' | 'manus' | 'chat' | 'logs' | 'health'

function App() {
  const [currentView, setCurrentView] = useState<View>('dashboard')

  const renderView = () => {
    switch (currentView) {
      case 'dashboard':
        return <Dashboard />
      case 'automation':
        return <Automation />
      case 'manus':
        return <ManusDashboard />
      case 'chat':
        return <ChatInterface />
      case 'logs':
        return <AuditLogs />
      case 'health':
        return <SystemHealth />
      default:
        return <Dashboard />
    }
  }

  return (
    <div className="flex h-screen bg-rich-navy text-white">
      {/* Animated Starfield Background */}
      <Starfield />

      {/* Shooting Stars Animation */}
      <ShootingStars />

      {/* Sidebar */}
      <div className="w-64 bg-rich-navy-light/30 backdrop-blur-md border-r border-white/10 flex flex-col relative z-10 shadow-2xl">
        {/* Logo/Header */}
        <div className="p-6 border-b border-white/10 bg-gradient-to-br from-white/5 to-transparent">
          <div className="flex items-center gap-3 mb-2">
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">O.R.E.L.I.U.S.</h1>
              <div className="h-0.5 w-full bg-gradient-to-r from-blue-400 via-blue-300 to-transparent"></div>
            </div>
          </div>
          <p className="text-xs text-white/60 uppercase tracking-wider font-semibold">Mission Control</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <button
            onClick={() => setCurrentView('dashboard')}
            className={`group w-full text-left px-4 py-3 rounded-xl mb-2 transition-all duration-300 ${
              currentView === 'dashboard'
                ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30 border border-white/20'
                : 'text-white/70 hover:bg-white/10 hover:text-white hover:border-white/20 border border-transparent'
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="font-semibold">Dashboard</span>
            </div>
          </button>

          <button
            onClick={() => setCurrentView('automation')}
            className={`group w-full text-left px-4 py-3 rounded-xl mb-2 transition-all duration-300 ${
              currentView === 'automation'
                ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30 border border-white/20'
                : 'text-white/70 hover:bg-white/10 hover:text-white hover:border-white/20 border border-transparent'
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="font-semibold">Automation</span>
            </div>
          </button>

          <button
            onClick={() => setCurrentView('manus')}
            className={`group w-full text-left px-4 py-3 rounded-xl mb-2 transition-all duration-300 ${
              currentView === 'manus'
                ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30 border border-white/20'
                : 'text-white/70 hover:bg-white/10 hover:text-white hover:border-white/20 border border-transparent'
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="font-semibold">Manus AI</span>
            </div>
          </button>

          <button
            onClick={() => setCurrentView('chat')}
            className={`group w-full text-left px-4 py-3 rounded-xl mb-2 transition-all duration-300 ${
              currentView === 'chat'
                ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30 border border-white/20'
                : 'text-white/70 hover:bg-white/10 hover:text-white hover:border-white/20 border border-transparent'
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="font-semibold">Chat</span>
            </div>
          </button>

          <button
            onClick={() => setCurrentView('health')}
            className={`group w-full text-left px-4 py-3 rounded-xl mb-2 transition-all duration-300 ${
              currentView === 'health'
                ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30 border border-white/20'
                : 'text-white/70 hover:bg-white/10 hover:text-white hover:border-white/20 border border-transparent'
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="font-semibold">System Health</span>
            </div>
          </button>

          <button
            onClick={() => setCurrentView('logs')}
            className={`group w-full text-left px-4 py-3 rounded-xl mb-2 transition-all duration-300 ${
              currentView === 'logs'
                ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30 border border-white/20'
                : 'text-white/70 hover:bg-white/10 hover:text-white hover:border-white/20 border border-transparent'
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="font-semibold">Audit Logs</span>
            </div>
          </button>
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-white/10 bg-gradient-to-t from-white/5 to-transparent">
          <div className="text-xs">
            <div className="mb-2 flex items-center gap-2">
              <div className="relative">
                <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse"></div>
                <div className="absolute inset-0 h-2 w-2 rounded-full bg-green-400/50 animate-ping"></div>
              </div>
              <span className="text-white/80 font-medium">Manus AI Active</span>
            </div>
            <div className="text-white/50 font-semibold">Version 0.4.0</div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden relative z-10">
        {renderView()}
      </div>
    </div>
  )
}

export default App
